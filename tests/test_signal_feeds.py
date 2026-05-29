"""Tests for the signal_feeds module."""
from __future__ import annotations

from src import signal_feeds


def test_import_builtin_pages(tmpdb):
    n = signal_feeds.import_builtin_pages()
    assert n == len(signal_feeds.BUILTIN_SUPPLIER_PAGES)


def test_import_builtin_pages_idempotent(tmpdb):
    n1 = signal_feeds.import_builtin_pages()
    n2 = signal_feeds.import_builtin_pages()
    assert n1 > 0
    assert n2 == 0


def test_record_and_query_alerts(tmpdb):
    alert_id = signal_feeds._record_alert(
        source_type="test",
        source_name="unit_test",
        ticker="SIVE",
        keyword="sole source",
        title="Test alert for SIVE",
        url="https://example.com",
        snippet="SIVE is the sole source for CPO lasers",
        priority="high",
    )
    assert alert_id > 0
    alerts = signal_feeds.unacknowledged_alerts()
    assert len(alerts) == 1
    assert alerts[0]["ticker"] == "SIVE"
    assert alerts[0]["alert_priority"] == "high"


def test_acknowledge_alert(tmpdb):
    signal_feeds._record_alert(
        "test", "unit_test", "XFAB", "CHIPS Act", "XFAB funding", "", "", "medium"
    )
    alerts = signal_feeds.unacknowledged_alerts()
    assert len(alerts) == 1
    signal_feeds.acknowledge_alert(alerts[0]["id"])
    assert signal_feeds.unacknowledged_alerts() == []


def test_keyword_check():
    assert signal_feeds._keyword_check("This is a sole source supplier", signal_feeds.SOLE_SOURCE_KEYWORDS) == "sole source"
    assert signal_feeds._keyword_check("nothing relevant here", signal_feeds.SOLE_SOURCE_KEYWORDS) is None


def test_keyword_check_case_insensitive():
    assert signal_feeds._keyword_check("CHIPS Act approved", signal_feeds.GOVT_KEYWORDS) == "CHIPS Act"
