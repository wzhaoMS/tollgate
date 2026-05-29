"""Schema tests for the initial-plan implementation foundation."""
from __future__ import annotations


def _tables(cx) -> set[str]:
    return {r[0] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(cx, table: str) -> set[str]:
    return {r[1] for r in cx.execute(f"PRAGMA table_info({table})")}


def test_initial_plan_foundation_tables_exist(tmpdb):
    expected = {
        "pipeline_runs",
        "signal_events",
        "serenity_signals",
        "supplier_relationships",
        "capacity_models",
        "substitution_assessments",
        "govt_awards",
        "float_short_interest",
        "catalyst_events",
        "position_sizing_decisions",
        "theme_exposures",
        "follower_history",
        "insider_option_events",
        "pair_trade_watchlist",
        "pair_trade_snapshots",
        "ma_floor_estimates",
        "consensus_metrics",
        "source_feed_status",
        "exit_plans",
    }
    assert expected <= _tables(tmpdb)


def test_serenity_signal_schema_supports_liquidity_trap(tmpdb):
    cols = _columns(tmpdb, "serenity_signals")
    assert {
        "ticker",
        "signaled_at",
        "source_url",
        "price_at_signal",
        "price_checked_at",
        "follower_count",
    } <= cols


def test_supplier_relationship_schema_tracks_customer_direction(tmpdb):
    cols = _columns(tmpdb, "supplier_relationships")
    assert {
        "supplier_ticker",
        "customer_name",
        "customer_ticker",
        "source_accession_no",
        "evidence_grade",
        "phrase",
        "direction",
    } <= cols


def test_capacity_and_sizing_schema_cover_plan_math(tmpdb):
    assert {"period", "supply_units", "demand_units", "gap_pct", "expansion_timeline_mo"} <= _columns(
        tmpdb, "capacity_models"
    )
    assert {"p_win", "avg_gain_pct", "p_loss", "avg_loss_pct", "capped_position_pct"} <= _columns(
        tmpdb, "position_sizing_decisions"
    )


def test_remaining_strategy_tables_cover_plan_upgrades(tmpdb):
    assert {"estimated_floor_usd", "current_market_cap_usd", "acquirers"} <= _columns(
        tmpdb, "ma_floor_estimates"
    )
    assert {"truth_score", "consensus_score", "analyst_coverage_count", "status"} <= _columns(
        tmpdb, "consensus_metrics"
    )
    assert {"source_name", "last_success_at", "status", "error_count"} <= _columns(
        tmpdb, "source_feed_status"
    )
    assert {"stop_loss_pct", "take_profit_1_pct", "stale_months"} <= _columns(tmpdb, "exit_plans")
    assert {"expiry_date", "estimated_value_usd", "status"} <= _columns(tmpdb, "insider_option_events")
