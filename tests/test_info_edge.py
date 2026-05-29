"""Tests for the info-edge gate."""
from __future__ import annotations

from src import scoring


def _seed(cx, ticker: str, mcap: float | None = None) -> None:
    cx.execute(
        "INSERT OR REPLACE INTO chokepoints (ticker, chokepoint, market_cap_usd) "
        "VALUES (?, 'x', ?)",
        (ticker, mcap),
    )
    cx.commit()


def _fund(cx, ticker: str, coverage: int | None) -> None:
    cx.execute(
        "INSERT OR REPLACE INTO fundamentals (ticker, sell_side_analysts) VALUES (?, ?)",
        (ticker, coverage),
    )
    cx.commit()


def test_info_edge_pass_small_cap_low_coverage(tmpdb):
    _seed(tmpdb, "TST", mcap=1_000_000_000)
    _fund(tmpdb, "TST", coverage=3)
    row = dict(tmpdb.execute("SELECT * FROM chokepoints WHERE ticker='TST'").fetchone())
    assert scoring._info_edge_signal(tmpdb, "TST", row) == "pass"


def test_info_edge_fail_megacap_with_coverage(tmpdb):
    _seed(tmpdb, "TST", mcap=200_000_000_000)
    _fund(tmpdb, "TST", coverage=30)
    row = dict(tmpdb.execute("SELECT * FROM chokepoints WHERE ticker='TST'").fetchone())
    assert scoring._info_edge_signal(tmpdb, "TST", row) == "fail"


def test_info_edge_watch_when_only_one_condition_met(tmpdb):
    _seed(tmpdb, "TST", mcap=200_000_000_000)
    _fund(tmpdb, "TST", coverage=2)
    row = dict(tmpdb.execute("SELECT * FROM chokepoints WHERE ticker='TST'").fetchone())
    assert scoring._info_edge_signal(tmpdb, "TST", row) == "watch"


def test_info_edge_unknown_when_no_data(tmpdb):
    _seed(tmpdb, "TST", mcap=None)
    row = dict(tmpdb.execute("SELECT * FROM chokepoints WHERE ticker='TST'").fetchone())
    assert scoring._info_edge_signal(tmpdb, "TST", row) == "unknown"
