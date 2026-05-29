"""Compute an M&A floor for chokepoint tickers from ``potential_acquirers``.

Serenity's heuristic (paraphrased): when (acquirer's strategic value gained
from owning the chokepoint) / (chokepoint's market cap) > 50, an acquisition
becomes a "when, not if" event. We translate that into a floor:

    floor_usd = max(2 * current_mcap, max_acquirer_strategic_value / 50)

Then ``scoring._ma_floor_signal`` reads ``ma_floor_estimates`` and passes
step 5 when floor_usd > 1.5 × current_mcap.
"""
from __future__ import annotations

from collections.abc import Iterable

from . import db

# Built-in acquirer seed for known chokepoint candidates. Strategic-value
# numbers are conservative estimates of the buyer's downside if they *can't*
# secure the supplier (e.g. losing a CPO program). Easy to tune later.
BUILTIN_ACQUIRERS: list[dict] = [
    # SIVE (Sivers) — CPO external laser
    {"target_ticker": "SIVE", "acquirer_name": "Marvell",  "acquirer_ticker": "MRVL", "strategic_value_usd": 1_000_000_000, "notes": "CPO program upside if Sivers locked in"},
    {"target_ticker": "SIVE", "acquirer_name": "Broadcom", "acquirer_ticker": "AVGO", "strategic_value_usd":   800_000_000, "notes": "CPO + DSP integration"},
    {"target_ticker": "SIVE", "acquirer_name": "Nokia",    "acquirer_ticker": "NOK",  "strategic_value_usd":   500_000_000, "notes": "Optical DCI alignment"},
    # XFAB — SiC/photonics foundry, CHIPS-recognized
    {"target_ticker": "XFAB", "acquirer_name": "NVIDIA",   "acquirer_ticker": "NVDA", "strategic_value_usd": 2_000_000_000, "notes": "photonicsFAB evaluation"},
    {"target_ticker": "XFAB", "acquirer_name": "GlobalFoundries", "acquirer_ticker": "GFS", "strategic_value_usd": 600_000_000, "notes": "US SiC capacity consolidation"},
    # AXTI — InP substrates
    {"target_ticker": "AXTI", "acquirer_name": "Coherent", "acquirer_ticker": "COHR", "strategic_value_usd": 800_000_000, "notes": "InP wafer vertical integration"},
    {"target_ticker": "AXTI", "acquirer_name": "Lumentum", "acquirer_ticker": "LITE", "strategic_value_usd": 600_000_000, "notes": "Substrate supply security"},
    # POET — photonics interposers
    {"target_ticker": "POET", "acquirer_name": "Foxconn",  "acquirer_ticker": None,    "strategic_value_usd": 400_000_000, "notes": "Optical interposer assembly"},
    # IQE — compound semi epi
    {"target_ticker": "IQE",  "acquirer_name": "Lumentum", "acquirer_ticker": "LITE", "strategic_value_usd": 500_000_000, "notes": "VCSEL epi vertical integration"},
    {"target_ticker": "IQE",  "acquirer_name": "Coherent", "acquirer_ticker": "COHR", "strategic_value_usd": 500_000_000, "notes": "Photonic device epi"},
    # WOLF — SiC
    {"target_ticker": "WOLF", "acquirer_name": "Infineon", "acquirer_ticker": None,    "strategic_value_usd": 3_000_000_000, "notes": "SiC EV/grid leadership"},
]


def record_acquirer(
    *,
    target_ticker: str,
    acquirer_name: str,
    strategic_value_usd: float,
    acquirer_ticker: str | None = None,
    evidence_url: str | None = None,
    notes: str | None = None,
) -> int:
    """Upsert a single acquirer row; returns row id (existing or new)."""
    db.init()
    with db.connect() as cx:
        cur = cx.execute(
            "INSERT INTO potential_acquirers "
            "(target_ticker, acquirer_name, acquirer_ticker, strategic_value_usd, evidence_url, notes) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(target_ticker, acquirer_name) DO UPDATE SET "
            "  acquirer_ticker = excluded.acquirer_ticker, "
            "  strategic_value_usd = excluded.strategic_value_usd, "
            "  evidence_url = excluded.evidence_url, "
            "  notes = excluded.notes, "
            "  recorded_at = datetime('now')",
            (
                target_ticker.upper(),
                acquirer_name,
                (acquirer_ticker or None) and acquirer_ticker.upper(),
                float(strategic_value_usd),
                evidence_url,
                notes,
            ),
        )
        return int(cur.lastrowid or 0)


def import_builtin_acquirers(rows: Iterable[dict] | None = None) -> int:
    rows = list(rows) if rows is not None else BUILTIN_ACQUIRERS
    n = 0
    for r in rows:
        record_acquirer(
            target_ticker=r["target_ticker"],
            acquirer_name=r["acquirer_name"],
            acquirer_ticker=r.get("acquirer_ticker"),
            strategic_value_usd=r["strategic_value_usd"],
            evidence_url=r.get("evidence_url"),
            notes=r.get("notes"),
        )
        n += 1
    return n


def compute_floor(ticker: str) -> dict | None:
    """Compute floor for one ticker. Returns ``None`` if no acquirers/mcap."""
    db.init()
    with db.connect() as cx:
        choke = cx.execute(
            "SELECT market_cap_usd FROM chokepoints WHERE ticker = ?", (ticker.upper(),)
        ).fetchone()
        if not choke or not choke["market_cap_usd"]:
            return None
        acquirers = cx.execute(
            "SELECT acquirer_name, strategic_value_usd FROM potential_acquirers "
            "WHERE target_ticker = ? ORDER BY strategic_value_usd DESC",
            (ticker.upper(),),
        ).fetchall()
        if not acquirers:
            return None
        mcap = float(choke["market_cap_usd"])
        max_strategic = max(float(a["strategic_value_usd"]) for a in acquirers)
        floor = max(2 * mcap, max_strategic / 50.0)
        names = ", ".join(a["acquirer_name"] for a in acquirers)
        cx.execute(
            "INSERT INTO ma_floor_estimates "
            "(ticker, estimated_floor_usd, current_market_cap_usd, acquirers, strategic_value_notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                ticker.upper(),
                floor,
                mcap,
                names,
                f"max_strategic_value_usd={max_strategic:.0f}; rule=max(2x_mcap, sv/50)",
            ),
        )
        return {
            "ticker": ticker.upper(),
            "estimated_floor_usd": floor,
            "current_market_cap_usd": mcap,
            "max_strategic_value_usd": max_strategic,
            "acquirers": names,
        }


def compute_all_floors() -> int:
    """Recompute floors for every chokepoint that has at least one acquirer.

    Returns the number of ma_floor_estimates rows inserted.
    """
    db.init()
    with db.connect() as cx:
        tickers = [
            r["target_ticker"]
            for r in cx.execute("SELECT DISTINCT target_ticker FROM potential_acquirers")
        ]
    n = 0
    for t in tickers:
        if compute_floor(t):
            n += 1
    return n
