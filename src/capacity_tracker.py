"""Capacity quarterly tracking — supply/demand gap time-series.

Tracks the chokepoint lifecycle: when the gap closes, pricing power collapses,
and the exit signal fires.
"""
from __future__ import annotations

from typing import Any

from . import db

# ─── Builtin seed data ──────────────────────────────────────────────────────
# Source: company annual reports, industry estimates, CMD presentations.
# These are approximate and should be refined with real filings data.
BUILTIN_CAPACITY_DATA: list[dict[str, Any]] = [
    # AXTI — InP substrates
    {"ticker": "AXTI", "quarter": "2025-Q3", "supply_units": 95000, "demand_units": 130000,
     "gap_pct": -26.9, "unit_label": "wafers/yr", "price_power": "high",
     "assumptions": "AXTI ~95k 4-inch equiv InP wafer capacity; demand from AAOI+Coherent+Lumentum transceiver ramp"},
    {"ticker": "AXTI", "quarter": "2025-Q4", "supply_units": 100000, "demand_units": 145000,
     "gap_pct": -31.0, "unit_label": "wafers/yr", "price_power": "very_high",
     "assumptions": "Demand surge from 800G/1.6T transceiver ramp; 12-18mo crystal growth lead time"},
    {"ticker": "AXTI", "quarter": "2026-Q2", "supply_units": 115000, "demand_units": 160000,
     "gap_pct": -28.1, "unit_label": "wafers/yr", "price_power": "very_high",
     "assumptions": "New furnace capacity coming online but demand still outpaces"},
    {"ticker": "AXTI", "quarter": "2027-Q2", "supply_units": 160000, "demand_units": 175000,
     "gap_pct": -8.6, "unit_label": "wafers/yr", "price_power": "neutral",
     "assumptions": "Major capacity expansion complete; gap narrowing signals exit window"},

    # SIVE — External CW lasers for CPO
    {"ticker": "SIVE", "quarter": "2025-Q3", "supply_units": 50000, "demand_units": 80000,
     "gap_pct": -37.5, "unit_label": "laser modules/yr", "price_power": "very_high",
     "assumptions": "Sivers sole-source to Ayar Labs; capacity constrained by InP fab"},
    {"ticker": "SIVE", "quarter": "2026-Q1", "supply_units": 65000, "demand_units": 110000,
     "gap_pct": -40.9, "unit_label": "laser modules/yr", "price_power": "very_high",
     "assumptions": "Ayar+Celestial AI ramp; Nokia likely customer per 2025 AR"},
    {"ticker": "SIVE", "quarter": "2027-Q1", "supply_units": 100000, "demand_units": 130000,
     "gap_pct": -23.1, "unit_label": "laser modules/yr", "price_power": "high",
     "assumptions": "CHIPS-funded expansion starting to yield; still supply constrained"},

    # XFAB — SiC foundry
    {"ticker": "XFAB", "quarter": "2025-Q3", "supply_units": 24000, "demand_units": 35000,
     "gap_pct": -31.4, "unit_label": "6-inch SiC wafers/mo", "price_power": "very_high",
     "assumptions": "XFAB sole US high-volume SiC foundry per NIST; auto+power demand"},
    {"ticker": "XFAB", "quarter": "2026-Q2", "supply_units": 30000, "demand_units": 42000,
     "gap_pct": -28.6, "unit_label": "6-inch SiC wafers/mo", "price_power": "high",
     "assumptions": "CHIPS Act $50M expansion underway; EV adoption accelerating"},
    {"ticker": "XFAB", "quarter": "2027-Q4", "supply_units": 48000, "demand_units": 50000,
     "gap_pct": -4.0, "unit_label": "6-inch SiC wafers/mo", "price_power": "neutral",
     "assumptions": "Full CHIPS expansion online; Wolfspeed also expanding"},

    # SOI — SOI substrates
    {"ticker": "SOI", "quarter": "2025-Q3", "supply_units": 1800000, "demand_units": 2400000,
     "gap_pct": -25.0, "unit_label": "200mm-equiv wafers/yr", "price_power": "high",
     "assumptions": "Soitec dominant SOI supplier; CPO + RF-SOI demand from TSMC/GF"},
    {"ticker": "SOI", "quarter": "2026-Q4", "supply_units": 2200000, "demand_units": 2700000,
     "gap_pct": -18.5, "unit_label": "200mm-equiv wafers/yr", "price_power": "high",
     "assumptions": "Bernin III expansion; auto legacy masking growth segment"},

    # IQE — Compound semiconductor epiwafers
    {"ticker": "IQE", "quarter": "2025-Q3", "supply_units": 280000, "demand_units": 360000,
     "gap_pct": -22.2, "unit_label": "epiwafers/yr", "price_power": "high",
     "assumptions": "IQE top-2 global epiwafer; VCSEL+photonics demand rising"},
]


def import_builtin_capacity() -> int:
    """Seed builtin capacity quarterly data. Returns rows inserted."""
    db.init()
    inserted = 0
    with db.connect() as cx:
        for row in BUILTIN_CAPACITY_DATA:
            try:
                cx.execute(
                    "INSERT OR IGNORE INTO capacity_quarterly "
                    "(ticker, quarter, supply_units, demand_units, gap_pct, "
                    " unit_label, price_power, assumptions) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["ticker"], row["quarter"], row["supply_units"],
                        row["demand_units"], row["gap_pct"], row["unit_label"],
                        row["price_power"], row["assumptions"],
                    ),
                )
                if cx.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except Exception:
                continue
    return inserted


def capacity_timeline(ticker: str) -> list[dict[str, Any]]:
    """Return quarterly capacity timeline for a ticker, oldest first."""
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT * FROM capacity_quarterly WHERE ticker = ? ORDER BY quarter",
            (ticker.upper(),),
        ).fetchall()
        return [dict(r) for r in rows]


def chokepoint_lifecycle(ticker: str) -> dict[str, Any] | None:
    """Analyze the lifecycle of a chokepoint based on capacity data.

    Returns dict with:
      - current_gap_pct: latest gap
      - gap_trend: 'widening', 'narrowing', 'stable'
      - estimated_close_quarter: when gap hits ~0%
      - exit_signal: True if gap is narrowing toward -5%
    """
    timeline = capacity_timeline(ticker)
    if len(timeline) < 2:
        return None

    latest = timeline[-1]
    prev = timeline[-2]

    current_gap = latest["gap_pct"] or 0
    prev_gap = prev["gap_pct"] or 0

    if current_gap < prev_gap - 2:
        trend = "widening"
    elif current_gap > prev_gap + 2:
        trend = "narrowing"
    else:
        trend = "stable"

    # Simple linear extrapolation for gap close
    close_quarter = None
    if trend == "narrowing" and current_gap < 0:
        gap_change_per_q = current_gap - prev_gap
        if gap_change_per_q > 0:
            quarters_to_close = abs(current_gap) / gap_change_per_q
            close_quarter = f"~{quarters_to_close:.0f} quarters from latest"

    exit_signal = trend == "narrowing" and current_gap > -10

    return {
        "ticker": ticker,
        "current_gap_pct": current_gap,
        "current_price_power": latest.get("price_power", "unknown"),
        "gap_trend": trend,
        "estimated_close": close_quarter,
        "exit_signal": exit_signal,
        "data_points": len(timeline),
    }


def all_lifecycles() -> list[dict[str, Any]]:
    """Compute lifecycle analysis for all tickers with capacity data."""
    db.init()
    with db.connect() as cx:
        tickers = [
            r["ticker"]
            for r in cx.execute(
                "SELECT DISTINCT ticker FROM capacity_quarterly ORDER BY ticker"
            ).fetchall()
        ]
    results = []
    for t in tickers:
        lc = chokepoint_lifecycle(t)
        if lc:
            results.append(lc)
    return results
