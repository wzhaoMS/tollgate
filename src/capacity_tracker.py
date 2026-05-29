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
    {"ticker": "IQE", "quarter": "2026-Q2", "supply_units": 310000, "demand_units": 380000,
     "gap_pct": -18.4, "unit_label": "epiwafers/yr", "price_power": "high",
     "assumptions": "Modest capacity expansion; Apple VCSEL orders normalizing"},
    {"ticker": "IQE", "quarter": "2027-Q2", "supply_units": 350000, "demand_units": 400000,
     "gap_pct": -12.5, "unit_label": "epiwafers/yr", "price_power": "neutral",
     "assumptions": "WIN Semi gaining share; gap narrowing toward equilibrium"},

    # POET — Optical interposer / CPO packaging
    {"ticker": "POET", "quarter": "2025-Q3", "supply_units": 30000, "demand_units": 45000,
     "gap_pct": -33.3, "unit_label": "interposers/yr", "price_power": "high",
     "assumptions": "POET sole-source optical interposer; Foxconn JV ramping"},
    {"ticker": "POET", "quarter": "2026-Q2", "supply_units": 55000, "demand_units": 80000,
     "gap_pct": -31.3, "unit_label": "interposers/yr", "price_power": "high",
     "assumptions": "Foxconn JV volume ramp; multiple design wins expected"},
    {"ticker": "POET", "quarter": "2027-Q2", "supply_units": 90000, "demand_units": 120000,
     "gap_pct": -25.0, "unit_label": "interposers/yr", "price_power": "high",
     "assumptions": "CPO adoption growing; POET capacity trailing demand"},

    # HPS-A — Data center power transformers
    {"ticker": "HPS-A", "quarter": "2025-Q3", "supply_units": 15000, "demand_units": 22000,
     "gap_pct": -31.8, "unit_label": "transformer units/yr", "price_power": "very_high",
     "assumptions": "Hammond Power: 18-24mo lead time; datacenter power backlog"},
    {"ticker": "HPS-A", "quarter": "2026-Q2", "supply_units": 18000, "demand_units": 28000,
     "gap_pct": -35.7, "unit_label": "transformer units/yr", "price_power": "very_high",
     "assumptions": "AI datacenter buildout accelerating demand; capacity constrained"},
    {"ticker": "HPS-A", "quarter": "2027-Q2", "supply_units": 25000, "demand_units": 32000,
     "gap_pct": -21.9, "unit_label": "transformer units/yr", "price_power": "high",
     "assumptions": "New manufacturing lines online; backlog slowly clearing"},

    # AEHR — SiC burn-in/test equipment
    {"ticker": "AEHR", "quarter": "2025-Q3", "supply_units": 120, "demand_units": 180,
     "gap_pct": -33.3, "unit_label": "FOX-XP systems/yr", "price_power": "high",
     "assumptions": "Aehr sole-source wafer-level burn-in; SiC customers ramping"},
    {"ticker": "AEHR", "quarter": "2026-Q2", "supply_units": 160, "demand_units": 220,
     "gap_pct": -27.3, "unit_label": "FOX-XP systems/yr", "price_power": "high",
     "assumptions": "SiC capacity buildout drives test demand; ON Semi, STMicro"},
    {"ticker": "AEHR", "quarter": "2027-Q2", "supply_units": 200, "demand_units": 240,
     "gap_pct": -16.7, "unit_label": "FOX-XP systems/yr", "price_power": "neutral",
     "assumptions": "Market maturing; competitor test approaches emerging"},
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
