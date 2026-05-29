"""Tests for schema migrations 3-5."""
from __future__ import annotations


def test_capacity_quarterly_table_exists(tmpdb):
    rows = tmpdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='capacity_quarterly'"
    ).fetchall()
    assert len(rows) == 1


def test_customer_supplier_pages_table_exists(tmpdb):
    rows = tmpdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='customer_supplier_pages'"
    ).fetchall()
    assert len(rows) == 1


def test_governance_events_table_exists(tmpdb):
    rows = tmpdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='governance_events'"
    ).fetchall()
    assert len(rows) == 1


def test_customer_warrants_table_exists(tmpdb):
    rows = tmpdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='customer_warrants'"
    ).fetchall()
    assert len(rows) == 1


def test_research_papers_table_exists(tmpdb):
    rows = tmpdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='research_papers'"
    ).fetchall()
    assert len(rows) == 1


def test_signal_feed_alerts_table_exists(tmpdb):
    rows = tmpdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='signal_feed_alerts'"
    ).fetchall()
    assert len(rows) == 1


def test_capacity_quarterly_price_power_check(tmpdb):
    """Check constraint on price_power column."""
    tmpdb.execute(
        "INSERT INTO capacity_quarterly (ticker, quarter, price_power) VALUES ('T', '2025-Q1', 'high')"
    )
    tmpdb.commit()
    row = tmpdb.execute("SELECT price_power FROM capacity_quarterly WHERE ticker='T'").fetchone()
    assert row[0] == "high"


def test_signal_feed_alerts_priority_check(tmpdb):
    """Check constraint on alert_priority column."""
    tmpdb.execute(
        "INSERT INTO signal_feed_alerts (source_type, source_name, alert_priority) VALUES ('test', 'test', 'critical')"
    )
    tmpdb.commit()
    row = tmpdb.execute("SELECT alert_priority FROM signal_feed_alerts").fetchone()
    assert row[0] == "critical"


def test_migrations_applied(tmpdb):
    """All 5 migrations should be recorded."""
    rows = tmpdb.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    versions = [r[0] for r in rows]
    assert 3 in versions
    assert 4 in versions
    assert 5 in versions
