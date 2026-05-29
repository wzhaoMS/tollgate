"""Tests for potential_acquirers + M&A floor computation."""
from __future__ import annotations

from src import ma_floor


def _seed_choke(cx, ticker: str, mcap: float) -> None:
    cx.execute(
        "INSERT OR REPLACE INTO chokepoints (ticker, chokepoint, market_cap_usd) "
        "VALUES (?, ?, ?)",
        (ticker, "x", mcap),
    )
    cx.commit()


def test_record_acquirer_upserts_and_imports_builtin(tmpdb):
    n = ma_floor.import_builtin_acquirers()
    assert n == len(ma_floor.BUILTIN_ACQUIRERS)
    # Idempotent on (target_ticker, acquirer_name)
    n2 = ma_floor.import_builtin_acquirers()
    assert n2 == n
    rows = tmpdb.execute(
        "SELECT target_ticker, COUNT(*) c FROM potential_acquirers GROUP BY target_ticker"
    ).fetchall()
    assert all(r["c"] >= 1 for r in rows)


def test_compute_floor_uses_50x_strategic_heuristic(tmpdb):
    _seed_choke(tmpdb, "TST", mcap=200_000_000)
    ma_floor.record_acquirer(
        target_ticker="TST",
        acquirer_name="BigCo",
        strategic_value_usd=20_000_000_000,  # /50 = 400M; > 2*200M = 400M
    )
    out = ma_floor.compute_floor("TST")
    assert out is not None
    assert out["estimated_floor_usd"] == 400_000_000
    persisted = tmpdb.execute(
        "SELECT estimated_floor_usd FROM ma_floor_estimates WHERE ticker = 'TST'"
    ).fetchone()
    assert persisted["estimated_floor_usd"] == 400_000_000


def test_compute_floor_returns_none_without_acquirers_or_mcap(tmpdb):
    _seed_choke(tmpdb, "TST", mcap=200_000_000)
    assert ma_floor.compute_floor("TST") is None
    # Acquirer but no mcap
    ma_floor.record_acquirer(
        target_ticker="EMPTY", acquirer_name="X", strategic_value_usd=1_000_000_000
    )
    assert ma_floor.compute_floor("EMPTY") is None


def test_compute_all_floors_processes_all_targets(tmpdb):
    _seed_choke(tmpdb, "AAA", mcap=100_000_000)
    _seed_choke(tmpdb, "BBB", mcap=200_000_000)
    ma_floor.record_acquirer(
        target_ticker="AAA", acquirer_name="X", strategic_value_usd=10_000_000_000
    )
    ma_floor.record_acquirer(
        target_ticker="BBB", acquirer_name="Y", strategic_value_usd=20_000_000_000
    )
    assert ma_floor.compute_all_floors() == 2
