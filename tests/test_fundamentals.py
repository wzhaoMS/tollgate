"""Tests for the fundamentals (condition 2.4) mispricing signal."""
from __future__ import annotations

from src import scoring


def _seed_choke(cx, ticker: str) -> None:
    cx.execute(
        "INSERT OR REPLACE INTO chokepoints (ticker, chokepoint, evidence_grade) "
        "VALUES (?, ?, 'A')",
        (ticker, "test"),
    )
    cx.commit()


def _seed_fund(cx, ticker: str, **fields) -> None:
    cols = ["ticker"] + list(fields.keys())
    placeholders = ",".join("?" for _ in cols)
    cx.execute(
        f"INSERT OR REPLACE INTO fundamentals ({','.join(cols)}) VALUES ({placeholders})",
        [ticker, *fields.values()],
    )
    cx.commit()


def test_mispricing_pass_when_cheap_and_fast_growing(tmpdb):
    _seed_fund(tmpdb, "TST", pb=1.2, pe=12, segment_growth_pct=35)
    assert scoring._mispricing_signal(tmpdb, "TST") == "pass"


def test_mispricing_fail_when_expensive_and_slow(tmpdb):
    _seed_fund(tmpdb, "TST", pb=8, pe=55, segment_growth_pct=5)
    assert scoring._mispricing_signal(tmpdb, "TST") == "fail"


def test_mispricing_watch_when_cheap_but_slow(tmpdb):
    _seed_fund(tmpdb, "TST", pb=1.5, pe=12, segment_growth_pct=5)
    assert scoring._mispricing_signal(tmpdb, "TST") == "watch"


def test_mispricing_unknown_when_no_row(tmpdb):
    assert scoring._mispricing_signal(tmpdb, "TST") == "unknown"


def test_mispricing_fail_demotes_buy_to_watch(tmpdb):
    _seed_choke(tmpdb, "TST")
    _seed_fund(tmpdb, "TST", pb=8, pe=55, segment_growth_pct=5)
    # Inject minimal evidence/score conditions: step_1 pass via evidence_log,
    # step_8 + step_9 via catalyst row + curated time-to-truth.
    tmpdb.execute(
        "INSERT INTO evidence_log (ticker, grade, source_url) VALUES ('TST','A','http://x')"
    )
    tmpdb.execute(
        "INSERT INTO catalyst_events (ticker, event_type, falsifiable, event_date, status) "
        "VALUES ('TST','earnings',1,date('now','+30 days'),'planned')"
    )
    tmpdb.execute(
        "UPDATE chokepoints SET time_to_truth_days = 90, capital_structure_flag = 'clean' "
        "WHERE ticker = 'TST'"
    )
    tmpdb.commit()

    row = dict(tmpdb.execute("SELECT * FROM chokepoints WHERE ticker = 'TST'").fetchone())
    out = scoring.score_row(tmpdb, row)
    assert out["step_1"] == "pass"
    assert out["step_8"] == "pass"
    assert out["step_9"] == "pass"
    assert out["mispricing"] == "fail"
    assert out["overall"] == "Watch"  # demoted from Buy
