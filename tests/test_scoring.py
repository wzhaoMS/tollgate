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
    assert scoring._govt_backstop(tmpdb, "TST", row) == "pass"


def test_govt_pass_from_filing_keyword_hits(tmpdb):
    tmpdb.execute(
        "INSERT INTO filings (accession_no, ticker, form, keyword_hits) "
        "VALUES ('f1', 'TST', '8-K', 'govt_backstop:CHIPS Act')",
    )
    tmpdb.commit()
    row = _chokepoint(tmpdb)
    assert scoring._govt_backstop(tmpdb, "TST", row) == "pass"


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
