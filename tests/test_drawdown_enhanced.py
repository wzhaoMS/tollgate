"""Tests for the enhanced drawdown module with fundamental triggers."""
from __future__ import annotations

from src import drawdown


def test_price_triggers_stop(tmpdb):
    tmpdb.execute("INSERT INTO positions (ticker, cost_basis, shares, last_price) VALUES ('TEST', 100, 10, 55)")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('TEST', 55)")
    tmpdb.commit()
    alerts = drawdown.evaluate()
    assert any("STOP" in a and "TEST" in a for a in alerts)


def test_price_triggers_tp1(tmpdb):
    tmpdb.execute("INSERT INTO positions (ticker, cost_basis, shares, last_price) VALUES ('TEST', 10, 10, 35)")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('TEST', 35)")
    tmpdb.commit()
    alerts = drawdown.evaluate()
    assert any("TP-1" in a and "TEST" in a for a in alerts)


def test_price_triggers_tp2(tmpdb):
    tmpdb.execute("INSERT INTO positions (ticker, cost_basis, shares, last_price) VALUES ('TEST', 10, 10, 65)")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('TEST', 65)")
    tmpdb.commit()
    alerts = drawdown.evaluate()
    assert any("TP-2" in a and "TEST" in a for a in alerts)


def test_coverage_trigger(tmpdb):
    tmpdb.execute("INSERT INTO positions (ticker, cost_basis, shares, last_price, opened_at) VALUES ('TEST', 10, 10, 15, '2024-01-01')")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('TEST', 15)")
    tmpdb.execute("INSERT INTO exit_plans (ticker, analyst_coverage_trim_threshold) VALUES ('TEST', 3)")
    tmpdb.execute("INSERT INTO fundamentals (ticker, sell_side_analysts) VALUES ('TEST', 5)")
    tmpdb.commit()
    alerts = drawdown.evaluate()
    assert any("COVERAGE" in a and "TEST" in a for a in alerts)


def test_gap_close_trigger(tmpdb):
    tmpdb.execute("INSERT INTO positions (ticker, cost_basis, shares, last_price, opened_at) VALUES ('TEST', 10, 10, 15, '2024-01-01')")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('TEST', 15)")
    tmpdb.execute("INSERT INTO exit_plans (ticker, capacity_gap_exit_pct) VALUES ('TEST', -5.0)")
    tmpdb.execute("INSERT INTO capacity_quarterly (ticker, quarter, supply_units, demand_units, gap_pct) VALUES ('TEST', '2025-Q3', 100, 102, -2.0)")
    tmpdb.commit()
    alerts = drawdown.evaluate()
    assert any("GAP-CLOSE" in a and "TEST" in a for a in alerts)


def test_ma_hold_signal(tmpdb):
    tmpdb.execute("INSERT INTO positions (ticker, cost_basis, shares, last_price, opened_at) VALUES ('TEST', 10, 10, 15, '2024-01-01')")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('TEST', 15)")
    tmpdb.execute("INSERT INTO governance_events (ticker, event_type, prior_ma_exp) VALUES ('TEST', 'board_appointment', 1)")
    tmpdb.commit()
    alerts = drawdown.evaluate()
    assert any("MA-HOLD" in a and "TEST" in a for a in alerts)


def test_no_alerts_for_normal_position(tmpdb):
    tmpdb.execute("INSERT INTO positions (ticker, cost_basis, shares, last_price, opened_at) VALUES ('TEST', 10, 10, 12, '2025-01-01')")
    tmpdb.execute("INSERT INTO contamination (ticker, last_close) VALUES ('TEST', 12)")
    tmpdb.commit()
    alerts = drawdown.evaluate()
    # Should have no price alerts (20% gain, no TP thresholds met)
    price_alerts = [a for a in alerts if a.startswith(("STOP", "TP-1", "TP-2", "TRAIL"))]
    assert len(price_alerts) == 0
