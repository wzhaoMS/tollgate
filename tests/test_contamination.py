"""Tests for the crowd-contamination flag math in the price scraper.

Uses the temp DB fixture; ``compute_contamination`` reads/writes via the
default ``db`` connection, which the fixture redirects to the temp file."""
from __future__ import annotations

from src.scrapers import yf_prices


def _seed_prices(cx, closes, volumes, ticker="TST"):
    assert len(closes) == len(volumes)
    for i, (c, v) in enumerate(zip(closes, volumes, strict=True)):
        cx.execute(
            "INSERT OR REPLACE INTO prices (ticker, date, close, volume) "
            "VALUES (?, date('now', ?), ?, ?)",
            (ticker, f"-{i} days", c, v),
        )
    cx.commit()


def test_contamination_none_when_insufficient(tmpdb):
    _seed_prices(tmpdb, [10.0, 10.0], [1, 1])
    assert yf_prices.compute_contamination("TST") is None


def test_contamination_high_on_sharp_5d_gain(tmpdb):
    # index 0 = latest. 25% above the close 5 trading days ago -> high.
    closes = [125.0, 120, 115, 110, 105, 100.0] + [100.0] * 20
    vols = [1_000_000] * len(closes)
    _seed_prices(tmpdb, closes, vols)
    res = yf_prices.compute_contamination("TST")
    assert res is not None
    assert res["crowd_flag"] == "high"
    assert round(res["pct_change_5d"], 1) == 25.0


def test_contamination_low_when_flat(tmpdb):
    closes = [100.0] * 26
    vols = [1_000_000] * 26
    _seed_prices(tmpdb, closes, vols)
    res = yf_prices.compute_contamination("TST")
    assert res is not None
    assert res["crowd_flag"] == "low"


def test_contamination_high_on_volume_spike(tmpdb):
    closes = [100.0] * 26
    # latest day volume 6x the trailing average -> volume_ratio >= 5 -> high.
    vols = [6_000_000] + [1_000_000] * 25
    _seed_prices(tmpdb, closes, vols)
    res = yf_prices.compute_contamination("TST")
    assert res is not None
    assert res["volume_ratio_20d"] >= 5
    assert res["crowd_flag"] == "high"
