"""Tests for the governance module."""
from __future__ import annotations

from src import governance


def test_import_builtin_events(tmpdb):
    n = governance.import_builtin_events()
    assert n == len(governance.BUILTIN_EVENTS)


def test_ma_signals_returns_ma_flagged(tmpdb):
    governance.import_builtin_events()
    signals = governance.ma_signals()
    # At least the SIVE board appointment with prior_ma_exp=1
    assert len(signals) >= 1
    tickers = {s["ticker"] for s in signals}
    assert "SIVE" in tickers


def test_ma_signals_by_ticker(tmpdb):
    governance.import_builtin_events()
    sive_signals = governance.ma_signals("SIVE")
    assert len(sive_signals) >= 1
    assert all(s["ticker"] == "SIVE" for s in sive_signals)


def test_recent_events(tmpdb):
    governance.import_builtin_events()
    events = governance.recent_events()
    assert len(events) == len(governance.BUILTIN_EVENTS)


def test_recent_events_by_ticker(tmpdb):
    governance.import_builtin_events()
    xfab_events = governance.recent_events("XFAB")
    assert len(xfab_events) >= 1
    assert all(e["ticker"] == "XFAB" for e in xfab_events)
