"""Tests for theme rotation map + RS signal."""
from __future__ import annotations

from src import rotation


def _seed_contam(cx, ticker: str, change_20d: float) -> None:
    cx.execute(
        "INSERT OR REPLACE INTO contamination (ticker, last_close, pct_change_20d) "
        "VALUES (?, 100, ?)",
        (ticker, change_20d),
    )
    cx.commit()


def test_import_builtin_stages_and_signal_hot(tmpdb):
    n = rotation.import_builtin_stages()
    assert n >= 1
    _seed_contam(tmpdb, "SIVE", 15.0)
    _seed_contam(tmpdb, "POET", 12.0)
    out = rotation.compute_rotation_signal()
    cpo = [s for s in out if s["theme"] == "CPO/external_lasers"][0]
    assert cpo["signal"] == "hot"
    assert cpo["avg_return_20d_pct"] == 13.5


def test_rotation_to_next_flag(tmpdb):
    rotation.import_builtin_stages()
    # stage 1 (optical) unwinding, stage 2 (CPO) hot
    for t in ("AAOI", "LITE", "COHR", "CIEN"):
        _seed_contam(tmpdb, t, -12.0)
    for t in ("SIVE", "POET", "CRDO", "ALAB"):
        _seed_contam(tmpdb, t, 10.0)
    out = rotation.compute_rotation_signal()
    optical = [s for s in out if s["theme"] == "optical_transceivers"][0]
    assert optical["rotation_to_next"] is True


def test_unknown_signal_when_no_prices(tmpdb):
    rotation.import_builtin_stages()
    out = rotation.compute_rotation_signal()
    assert all(s["signal"] == "unknown" for s in out)
