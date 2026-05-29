"""Tests for strategy support modules beyond the core scorecard."""
from __future__ import annotations

from src import exit_plan, pair_trade, source_health, strategy_signals


def test_true_vs_consensus_detects_hidden_truth(tmpdb):
    tmpdb.execute(
        "INSERT INTO consensus_metrics "
        "(ticker, truth_score, consensus_score, analyst_coverage_count) "
        "VALUES ('TST', 0.9, 0.2, 1)"
    )
    tmpdb.commit()
    assert strategy_signals.true_vs_consensus("TST") == "hidden_truth"


def test_reverse_crowd_alerts_require_follower_growth_and_small_cap_signal(tmpdb):
    tmpdb.execute(
        "INSERT INTO chokepoints (ticker, market_cap_usd) VALUES ('TST', 1000000000)"
    )
    tmpdb.execute(
        "INSERT INTO serenity_signals (ticker, handle, tweet_id, signaled_at, price_at_signal) "
        "VALUES ('TST', 'aleabitoreddit', 'tw1', datetime('now', '-1 day'), 10.0)"
    )
    tmpdb.execute(
        "INSERT INTO follower_history (handle, observed_at, follower_count) "
        "VALUES ('aleabitoreddit', datetime('now', '-7 days'), 100000)"
    )
    tmpdb.execute(
        "INSERT INTO follower_history (handle, observed_at, follower_count) "
        "VALUES ('aleabitoreddit', datetime('now'), 120000)"
    )
    tmpdb.commit()
    alerts = strategy_signals.reverse_crowd_alerts(growth_threshold_pct=15)
    assert alerts and alerts[0]["ticker"] == "TST"
    assert alerts[0]["signal"] == "reverse_watch"


def test_source_health_records_failures_and_recovers(tmpdb):
    source_health.record_source_status("chips.gov", source_type="government", ok=False, error="timeout")
    assert source_health.stale_or_failed_sources()[0]["source_name"] == "chips.gov"
    source_health.record_source_status("chips.gov", source_type="government", ok=True)
    assert source_health.stale_or_failed_sources() == []


def test_pair_watchlist_sync_persists_candidates(tmpdb):
    tmpdb.execute("INSERT INTO chokepoints (ticker, chokepoint) VALUES ('LONG', 'SiC foundry')")
    tmpdb.execute("INSERT INTO chokepoints (ticker, chokepoint) VALUES ('SHORT', 'SiC foundry')")
    tmpdb.execute(
        "INSERT INTO contamination (ticker, pct_change_20d, crowd_flag) VALUES ('LONG', -5, 'low')"
    )
    tmpdb.execute(
        "INSERT INTO contamination (ticker, pct_change_20d, crowd_flag) VALUES ('SHORT', 40, 'high')"
    )
    tmpdb.commit()
    assert pair_trade.sync_watchlist(limit=1) == 1
    assert pair_trade.sync_watchlist(limit=1) == 0
    row = tmpdb.execute("SELECT long_ticker, short_ticker FROM pair_trade_watchlist").fetchone()
    assert row["long_ticker"] == "LONG"
    assert row["short_ticker"] == "SHORT"


def test_pair_hedge_and_snapshot_pnl(tmpdb):
    assert pair_trade.hedge_notional(10_000) == {
        "long_notional": 5_000,
        "short_notional": 5_000,
        "gross_notional": 10_000,
    }
    tmpdb.execute(
        "INSERT INTO pair_trade_watchlist (theme, long_ticker, short_ticker) VALUES ('sic', 'LONG', 'SHORT')"
    )
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('LONG', 10)")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('SHORT', 20)")
    tmpdb.commit()
    assert pair_trade.record_snapshots() == 1
    tmpdb.execute("UPDATE contamination SET last_close = 12 WHERE ticker = 'LONG'")
    tmpdb.execute("UPDATE contamination SET last_close = 18 WHERE ticker = 'SHORT'")
    tmpdb.commit()
    assert pair_trade.record_snapshots() == 1
    row = tmpdb.execute(
        "SELECT pnl_pct FROM pair_trade_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["pnl_pct"] == 15.0


def test_exit_plan_created_for_open_position(tmpdb):
    tmpdb.execute(
        "INSERT INTO positions (ticker, cost_basis, shares, high_water, last_price, pnl_pct) "
        "VALUES ('TST', 10, 1, 10, 10, 0)"
    )
    tmpdb.commit()
    assert exit_plan.missing_exit_plans() == ["TST"]
    assert exit_plan.ensure_for_open_positions() == 1
    plan = tmpdb.execute("SELECT stop_loss_pct, take_profit_1_pct FROM exit_plans WHERE ticker = 'TST'").fetchone()
    assert plan["stop_loss_pct"] == -40.0
    assert plan["take_profit_1_pct"] == 200.0
