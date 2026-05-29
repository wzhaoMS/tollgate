"""Seed the sub-$10B DELL/AI-upstream screen candidates into ``chokepoints``.

These are the names surfaced by the market-cap screen as possible
"next SIVE" alternatives once SIVE itself grew past ~$20B. The point of
seeding them is to run the *evidence-based* 9/11-step scoring engine over
them instead of a narrative ranking.

IMPORTANT: brand-new names (LPK, AEHR, BELFB, VSH, POWL) are seeded with
``evidence_grade='U'`` and no fabricated capacity/substitution data, so the
scoring engine honestly returns ``unknown`` for steps we have not verified.
Market caps are normalized to USD from the live screen (approximate).
"""
from __future__ import annotations

from . import db

# Approximate FX used to normalize the screen caps to USD.
_EUR_USD = 1.08
_GBP_USD = 1.27
_CAD_USD = 0.73

# ─── screen candidates ──────────────────────────────────────────────────────
# market_cap_usd values are normalized to USD from the live screen.
BUILTIN_CANDIDATES: list[dict] = [
    # Brand-new names (no verified evidence yet -> grade 'U').
    {
        "ticker": "LPK",
        "chokepoint": "Glass-core / advanced PCB laser tooling (LPKF)",
        "end_customer": "DELL/AI-server PCB & substrate makers (unverified)",
        "evidence_grade": "U",
        "capacity_gap_pct": None,
        "expansion_timeline_mo": None,
        "substitutes": "Mechanical drilling, mSAP — partial substitutes exist",
        "market_cap_usd": round(541_000_000 * _EUR_USD),
        "next_catalyst": "Glass-core PCB adoption updates; tooling orders",
        "crowdedness": "low",
        "capital_structure_flag": "unknown",
        "decision": "Watch",
        "notes": "Smallest/weirdest screen name; glass-core tooling angle unverified.",
    },
    {
        "ticker": "AEHR",
        "chokepoint": "SiC wafer-level burn-in / test equipment",
        "end_customer": "SiC device makers feeding AI/EV power (unverified)",
        "evidence_grade": "U",
        "capacity_gap_pct": None,
        "expansion_timeline_mo": None,
        "substitutes": "Package-level test; in-house test rigs",
        "market_cap_usd": 2_900_000_000,
        "next_catalyst": "SiC test-system bookings; customer concentration disclosure",
        "crowdedness": "medium",
        "capital_structure_flag": "unknown",
        "decision": "Watch",
        "notes": "Second-derivative SiC capacity play; not DELL-direct.",
    },
    {
        "ticker": "BELFB",
        "chokepoint": "Power/connectivity components for servers",
        "end_customer": "Server/datacenter OEMs incl. DELL (unverified)",
        "evidence_grade": "U",
        "capacity_gap_pct": None,
        "expansion_timeline_mo": None,
        "substitutes": "Many competing component vendors",
        "market_cap_usd": 3_900_000_000,
        "next_catalyst": "Datacenter power backlog; customer concentration",
        "crowdedness": "medium",
        "capital_structure_flag": "unknown",
        "decision": "Watch",
        "notes": "Server-adjacent but weak chokepoint quality unless concentration proves it.",
    },
    {
        "ticker": "VSH",
        "chokepoint": "Discretes/passives for AI power supply chains",
        "end_customer": "Broad electronics incl. AI power (unverified)",
        "evidence_grade": "U",
        "capacity_gap_pct": None,
        "expansion_timeline_mo": None,
        "substitutes": "Highly substitutable commodity components",
        "market_cap_usd": 7_100_000_000,
        "next_catalyst": "AI power demand cycle",
        "crowdedness": "high",
        "capital_structure_flag": "unknown",
        "decision": "Skip",
        "notes": "Cyclical component supplier, not a chokepoint.",
    },
    {
        "ticker": "POWL",
        "chokepoint": "Electrical gear for datacenter power infrastructure",
        "end_customer": "Datacenter/utility power buildout (unverified)",
        "evidence_grade": "U",
        "capacity_gap_pct": None,
        "expansion_timeline_mo": None,
        "substitutes": "Other electrical-gear OEMs (Eaton, Hubbell)",
        "market_cap_usd": 10_400_000_000,
        "next_catalyst": "Datacenter power backlog conversion",
        "crowdedness": "high",
        "capital_structure_flag": "unknown",
        "decision": "Skip",
        "notes": "Over $10B; real bottleneck but already discovered/crowded.",
    },
    # Existing names: refresh live USD market cap from the screen so the
    # info-edge / M&A-floor steps use current numbers.
    {"ticker": "POET", "market_cap_usd": 2_100_000_000},
    {"ticker": "XFAB", "market_cap_usd": round(1_400_000_000 * _EUR_USD)},
    {"ticker": "IQE", "market_cap_usd": round(465_000_000 * _GBP_USD)},
    {"ticker": "SOI", "market_cap_usd": round(6_300_000_000 * _EUR_USD)},
    {"ticker": "AXTI", "market_cap_usd": 6_700_000_000},
    {"ticker": "HPS-A", "market_cap_usd": round(3_900_000_000 * _CAD_USD)},
]


def import_builtin_candidates() -> int:
    """Upsert all screen candidates into ``chokepoints``. Returns row count."""
    db.init()
    n = 0
    with db.connect() as cx:
        for row in BUILTIN_CANDIDATES:
            db.upsert_chokepoint(cx, row)
            n += 1
    return n
