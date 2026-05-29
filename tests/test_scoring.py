"""Unit tests for the scoring engine's individual signal functions and the
overall verdict logic. These are pure functions over a SQLite connection, so
they run fully offline."""
from __future__ import annotations

from src import scoring


def _chokepoint(cx, **over):
    base = {
        "ticker": "TST",
        "crowdedness": "low",
        "capital_structure_flag": "clean",
        "evidence_grade": "U",
        "catalyst_score": 8,
        "time_to_truth_days": 100,
        "capacity_gap_pct": None,
        "expansion_timeline_mo": None,
        "market_cap_usd": None,
        "revenue_ttm_usd": None,
        "next_catalyst": None,
        "notes": None,
        "demand_proxy": None,
        "capacity": None,
    }
    base.update(over)
    return base


# ---- insider signal -------------------------------------------------------

def _add_insider(cx, code, amount, days_ago=10, ticker="TST", filer="A"):
    cx.execute(
        "INSERT INTO insider_txns "
        "(accession_no, ticker, filer_name, txn_date, txn_code, dollar_amount) "
        "VALUES (?, ?, ?, date('now', ?), ?, ?)",
        (f"acc-{code}-{amount}-{days_ago}", ticker, filer, f"-{days_ago} days", code, amount),
    )
    cx.commit()


def test_insider_unknown_when_no_rows(tmpdb):
    assert scoring._insider_signal(tmpdb, "TST") == "unknown"


def test_insider_pass_on_net_buying(tmpdb):
    _add_insider(tmpdb, "P", 500_000)
    _add_insider(tmpdb, "S", 100_000)
    assert scoring._insider_signal(tmpdb, "TST") == "pass"


def test_insider_fail_on_net_selling(tmpdb):
    _add_insider(tmpdb, "P", 100_000)
    _add_insider(tmpdb, "S", 900_000)
    assert scoring._insider_signal(tmpdb, "TST") == "fail"


def test_insider_watch_when_only_non_open_market(tmpdb):
    # Code 'A' (grant) etc. are not open-market buys/sells.
    _add_insider(tmpdb, "A", 50_000)
    assert scoring._insider_signal(tmpdb, "TST") == "watch"


def test_insider_ignores_stale_transactions(tmpdb):
    _add_insider(tmpdb, "P", 1_000_000, days_ago=400)
    assert scoring._insider_signal(tmpdb, "TST", lookback_days=180) == "unknown"


def test_insider_prefers_key_executive_activity(tmpdb):
    _add_insider(tmpdb, "P", 100_000, filer="A")
    tmpdb.execute(
        "INSERT INTO insider_txns "
        "(accession_no, ticker, filer_name, relation, txn_date, txn_code, dollar_amount) "
        "VALUES ('acc-key', 'TST', 'CEO PERSON', 'Chief Executive Officer', date('now'), 'S', 900000)"
    )
    tmpdb.commit()
    assert scoring._insider_signal(tmpdb, "TST") == "fail"


def test_insider_watch_on_upcoming_option_expiry_without_transactions(tmpdb):
    tmpdb.execute(
        "INSERT INTO insider_option_events (ticker, insider_name, expiry_date, status) "
        "VALUES ('TST', 'CEO PERSON', date('now', '+30 days'), 'open')"
    )
    tmpdb.commit()
    assert scoring._insider_signal(tmpdb, "TST") == "watch"


# ---- liquidity ------------------------------------------------------------

def _add_prices(cx, closes_vols, ticker="TST"):
    for i, (c, v) in enumerate(closes_vols):
        cx.execute(
            "INSERT OR REPLACE INTO prices (ticker, date, close, volume) "
            "VALUES (?, date('now', ?), ?, ?)",
            (ticker, f"-{i} days", c, v),
        )
    cx.commit()


def test_liquidity_unknown_without_data(tmpdb):
    assert scoring._liquidity(tmpdb, "TST") == "unknown"


def test_liquidity_pass_high_dollar_volume(tmpdb):
    _add_prices(tmpdb, [(100.0, 1_000_000)] * 20)  # $100M/day
    assert scoring._liquidity(tmpdb, "TST") == "pass"


def test_liquidity_watch_mid(tmpdb):
    _add_prices(tmpdb, [(10.0, 200_000)] * 20)  # $2M/day
    assert scoring._liquidity(tmpdb, "TST") == "watch"


def test_liquidity_fail_illiquid(tmpdb):
    _add_prices(tmpdb, [(1.0, 100_000)] * 20)  # $100k/day
    assert scoring._liquidity(tmpdb, "TST") == "fail"


# ---- government backstop --------------------------------------------------

def test_govt_unknown_without_evidence(tmpdb):
    row = _chokepoint(tmpdb)
    assert scoring._govt_backstop(tmpdb, "TST", row) == "unknown"


def test_govt_pass_from_curated_text(tmpdb):
    row = _chokepoint(tmpdb, notes="Received a CHIPS Act preliminary memorandum of terms.")
    assert scoring._govt_backstop(tmpdb, "TST", row) == "watch"


def test_govt_pass_from_filing_keyword_hits(tmpdb):
    tmpdb.execute(
        "INSERT INTO filings (accession_no, ticker, form, keyword_hits) "
        "VALUES ('f1', 'TST', '8-K', 'govt_backstop:CHIPS Act')",
    )
    tmpdb.commit()
    row = _chokepoint(tmpdb)
    assert scoring._govt_backstop(tmpdb, "TST", row) == "watch"


def test_govt_pass_from_official_award(tmpdb):
    tmpdb.execute(
        "INSERT INTO govt_awards (ticker, agency, award_amount_usd, official_url) "
        "VALUES ('TST', 'CHIPS Program Office', 12000000, 'https://chips.gov/example')",
    )
    tmpdb.commit()
    row = _chokepoint(tmpdb)
    assert scoring._govt_backstop(tmpdb, "TST", row) == "pass"


# ---- initial plan checklist fidelity -------------------------------------

def test_serenity_liquidity_trap_fails_stale_post_signal_move(tmpdb):
    tmpdb.execute(
        "INSERT INTO serenity_signals (ticker, signaled_at, price_at_signal) "
        "VALUES ('TST', datetime('now', '-2 days'), 10.0)"
    )
    tmpdb.execute(
        "INSERT INTO contamination (ticker, last_close, crowd_flag) VALUES ('TST', 12.0, 'low')"
    )
    tmpdb.commit()
    assert scoring._serenity_liquidity_trap(tmpdb, "TST") == "fail"


def test_supplier_relationship_upgrades_step1(tmpdb):
    tmpdb.execute(
        "INSERT INTO supplier_relationships "
        "(supplier_ticker, customer_name, evidence_grade, direction, phrase) "
        "VALUES ('TST', 'Hyperscaler Y', 'A', 'customer_to_supplier', 'sole supplier')"
    )
    tmpdb.commit()
    row = _chokepoint(tmpdb)
    out = scoring.score_row(tmpdb, row)
    assert out["step_1"] == "pass"


def test_capacity_model_overrides_curated_capacity_row(tmpdb):
    tmpdb.execute(
        "INSERT INTO capacity_models (ticker, period, supply_units, demand_units, gap_pct, expansion_timeline_mo) "
        "VALUES ('TST', '2026Q4', 100, 140, 40, 18)"
    )
    tmpdb.commit()
    row = _chokepoint(tmpdb, capacity_gap_pct=None, expansion_timeline_mo=None)
    assert scoring._capacity_signal(tmpdb, "TST", row) == "pass"


def test_substitution_requires_two_short_term_blockers(tmpdb):
    tmpdb.execute(
        "INSERT INTO substitution_assessments "
        "(ticker, short_term_non_substitutable_count, status) VALUES ('TST', 2, 'unknown')"
    )
    tmpdb.commit()
    assert scoring._substitution_risk(tmpdb, "TST") == "pass"


def test_float_liquidity_fails_when_exit_takes_too_long(tmpdb):
    tmpdb.execute(
        "INSERT INTO float_short_interest (ticker, days_to_exit, short_interest_pct) "
        "VALUES ('TST', 6.0, 5.0)"
    )
    tmpdb.commit()
    assert scoring._float_exit_liquidity(tmpdb, "TST") == "fail"


def test_catalyst_event_passes_when_falsifiable_inside_90_days(tmpdb):
    tmpdb.execute(
        "INSERT INTO catalyst_events (ticker, event_date, event_type, description, falsifiable) "
        "VALUES ('TST', date('now', '+30 days'), 'earnings', 'customer ramp update', 1)"
    )
    tmpdb.commit()
    row = _chokepoint(tmpdb, catalyst_score=None)
    assert scoring._catalyst_signal(tmpdb, "TST", row) == "pass"


def test_ma_floor_estimate_passes_when_floor_exceeds_1_5x_market_cap(tmpdb):
    tmpdb.execute(
        "INSERT INTO ma_floor_estimates (ticker, estimated_floor_usd, current_market_cap_usd) "
        "VALUES ('TST', 1800000000, 1000000000)"
    )
    tmpdb.commit()
    row = _chokepoint(tmpdb, market_cap_usd=1_000_000_000, revenue_ttm_usd=100_000_000)
    assert scoring._ma_floor_signal(tmpdb, "TST", row) == "pass"


# ---- overall verdict ------------------------------------------------------

def test_verdict_pass_on_hard_fail(tmpdb):
    # crowdedness=high -> step_minus1 fail -> overall Pass (skip the name)
    row = _chokepoint(tmpdb, crowdedness="high")
    out = scoring.score_row(tmpdb, row)
    assert out["step_minus1"] == "fail"
    assert out["overall"] == "Pass"


def test_verdict_buy_on_strong_setup(tmpdb):
    # A-grade evidence + catalyst + near-term + liquid + no insider selling.
    tmpdb.execute(
        "INSERT INTO evidence_log (ticker, grade, excerpt) VALUES ('TST','A','sole source')"
    )
    _add_prices(tmpdb, [(100.0, 1_000_000)] * 20)
    _add_insider(tmpdb, "P", 100_000)
    tmpdb.commit()
    row = _chokepoint(tmpdb)
    out = scoring.score_row(tmpdb, row)
    assert out["step_1"] == "pass"
    assert out["overall"] == "Buy"


def test_verdict_watch_when_insiders_selling(tmpdb):
    tmpdb.execute(
        "INSERT INTO evidence_log (ticker, grade, excerpt) VALUES ('TST','A','sole source')"
    )
    _add_prices(tmpdb, [(100.0, 1_000_000)] * 20)
    _add_insider(tmpdb, "S", 1_000_000)
    tmpdb.commit()
    row = _chokepoint(tmpdb)
    out = scoring.score_row(tmpdb, row)
    assert out["step_1"] == "pass"
    assert out["step_6"] == "fail"
    assert out["overall"] == "Watch"


# ---- score persistence semantics -----------------------------------------

def test_compute_all_does_not_persist_scores(tmpdb):
    tmpdb.execute("INSERT INTO chokepoints (ticker, crowdedness) VALUES ('TST', 'low')")
    tmpdb.commit()
    out = scoring.compute_all()
    assert len(out) == 1
    assert tmpdb.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 0


def test_score_all_persists_when_requested(tmpdb):
    tmpdb.execute("INSERT INTO chokepoints (ticker, crowdedness) VALUES ('TST', 'low')")
    tmpdb.commit()
    out = scoring.score_all(persist=True)
    assert len(out) == 1
    assert tmpdb.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 1


def test_latest_scores_reads_persisted_rows_without_adding_new_ones(tmpdb):
    tmpdb.execute("INSERT INTO chokepoints (ticker, crowdedness) VALUES ('TST', 'low')")
    tmpdb.execute("INSERT INTO scores (ticker, step_minus1, overall) VALUES ('TST', 'pass', 'Watch')")
    tmpdb.commit()
    out = scoring.latest_scores()
    assert out[0]["ticker"] == "TST"
    assert tmpdb.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 1
