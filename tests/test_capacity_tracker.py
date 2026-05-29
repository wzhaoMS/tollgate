"""Tests for the capacity_tracker module."""
from __future__ import annotations

from src import capacity_tracker


def test_import_builtin_capacity(tmpdb):
    n = capacity_tracker.import_builtin_capacity()
    assert n == len(capacity_tracker.BUILTIN_CAPACITY_DATA)
    # Check AXTI has multiple quarters
    timeline = capacity_tracker.capacity_timeline("AXTI")
    assert len(timeline) >= 3


def test_import_builtin_is_idempotent(tmpdb):
    n1 = capacity_tracker.import_builtin_capacity()
    n2 = capacity_tracker.import_builtin_capacity()
    assert n1 > 0
    assert n2 == 0


def test_capacity_timeline_returns_ordered(tmpdb):
    capacity_tracker.import_builtin_capacity()
    timeline = capacity_tracker.capacity_timeline("SIVE")
    quarters = [t["quarter"] for t in timeline]
    assert quarters == sorted(quarters)


def test_chokepoint_lifecycle_needs_two_points(tmpdb):
    capacity_tracker.import_builtin_capacity()
    # AXTI has 4 data points → should work
    lc = capacity_tracker.chokepoint_lifecycle("AXTI")
    assert lc is not None
    assert lc["ticker"] == "AXTI"
    assert lc["data_points"] >= 2
    assert lc["gap_trend"] in ("widening", "narrowing", "stable")


def test_chokepoint_lifecycle_detects_narrowing(tmpdb):
    capacity_tracker.import_builtin_capacity()
    # AXTI goes from -26.9 → -31.0 → -28.1 → -8.6 → last two are narrowing
    lc = capacity_tracker.chokepoint_lifecycle("AXTI")
    assert lc is not None
    assert lc["gap_trend"] == "narrowing"
    assert lc["exit_signal"] is True  # gap is -8.6%, above -10%


def test_all_lifecycles(tmpdb):
    capacity_tracker.import_builtin_capacity()
    lcs = capacity_tracker.all_lifecycles()
    tickers = {lc["ticker"] for lc in lcs}
    # AXTI, SIVE, XFAB, SOI all have ≥2 data points
    assert "AXTI" in tickers
    assert "SIVE" in tickers


def test_empty_timeline_returns_empty(tmpdb):
    timeline = capacity_tracker.capacity_timeline("NONEXISTENT")
    assert timeline == []


def test_lifecycle_returns_none_with_no_data(tmpdb):
    lc = capacity_tracker.chokepoint_lifecycle("NONEXISTENT")
    assert lc is None
