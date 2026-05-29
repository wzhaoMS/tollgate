"""Obvious-trade -> supplier graph (Layer D of the first-principles checklist).

The literal one-line first principle is:

    Trade the supplier of the obvious trade.

This module models the inverse-lookup graph:

    obvious_ticker (e.g. NVDA, MRVL, AVGO, AMZN)
        -> [(supplier_ticker, link_strength, evidence_url), ...]

Schema lives in a small migration-style table created on demand.

Usage::

    py -m src.cli supplychain --builtin
    py -m src.cli supplychain --for NVDA

The ``--for`` query returns the upstream suppliers ranked by ``link_strength``
joined with each supplier's latest score so we can see, at a glance, which
upstream small-cap is the strongest chokepoint for the obvious trade.
"""
from __future__ import annotations

from . import db

BUILTIN_LINKS: list[dict] = [
    # NVDA needs ...
    {"obvious_ticker": "NVDA", "supplier_ticker": "XFAB", "link_strength": 0.9, "rationale": "SiC photonicsFAB evaluation; CHIPS-recognized US foundry"},
    {"obvious_ticker": "NVDA", "supplier_ticker": "AXTI", "link_strength": 0.7, "rationale": "InP substrates feed LITE/COHR optical modules"},
    {"obvious_ticker": "NVDA", "supplier_ticker": "WOLF", "link_strength": 0.6, "rationale": "SiC for power delivery in AI racks"},
    {"obvious_ticker": "NVDA", "supplier_ticker": "POET", "link_strength": 0.5, "rationale": "Photonic interposers for optical I/O"},
    # MRVL needs ...
    {"obvious_ticker": "MRVL", "supplier_ticker": "SIVE", "link_strength": 0.9, "rationale": "CPO external laser; potential acquisition target"},
    {"obvious_ticker": "MRVL", "supplier_ticker": "SOI",  "link_strength": 0.7, "rationale": "SOI substrates for photonics integration"},
    {"obvious_ticker": "MRVL", "supplier_ticker": "TSEM", "link_strength": 0.6, "rationale": "Specialty silicon for Marvell custom ASICs"},
    # AVGO needs ...
    {"obvious_ticker": "AVGO", "supplier_ticker": "SIVE", "link_strength": 0.7, "rationale": "Optical I/O laser supplier"},
    {"obvious_ticker": "AVGO", "supplier_ticker": "IQE",  "link_strength": 0.6, "rationale": "Compound semi epi for VCSELs/photonics"},
    # AMZN data center electrification ...
    {"obvious_ticker": "AMZN", "supplier_ticker": "HPS-A","link_strength": 0.7, "rationale": "Hammond transformers for hyperscaler DCs"},
    {"obvious_ticker": "AMZN", "supplier_ticker": "VST",  "link_strength": 0.6, "rationale": "Independent power for DC build-out"},
    {"obvious_ticker": "AMZN", "supplier_ticker": "CEG",  "link_strength": 0.6, "rationale": "Nuclear PPA for AI power demand"},
    # MSFT ...
    {"obvious_ticker": "MSFT", "supplier_ticker": "CEG",  "link_strength": 0.7, "rationale": "Three Mile Island restart PPA"},
    {"obvious_ticker": "MSFT", "supplier_ticker": "AAOI", "link_strength": 0.5, "rationale": "Maia optical interconnect"},
    # AAOI as obvious -> upstream ...
    {"obvious_ticker": "AAOI", "supplier_ticker": "AXTI", "link_strength": 0.85, "rationale": "InP substrate sole-source for AAOI's modules"},
    {"obvious_ticker": "AAOI", "supplier_ticker": "IQE",  "link_strength": 0.6, "rationale": "Epi wafer supply"},
]


def init() -> None:
    db.init()
    with db.connect() as cx:
        cx.executescript(
            """
            CREATE TABLE IF NOT EXISTS obvious_trade_supply_chain (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                obvious_ticker      TEXT NOT NULL,
                supplier_ticker     TEXT NOT NULL,
                link_strength       REAL NOT NULL DEFAULT 0.5,
                rationale           TEXT,
                evidence_url        TEXT,
                recorded_at         TEXT DEFAULT (datetime('now')),
                UNIQUE(obvious_ticker, supplier_ticker)
            );
            CREATE INDEX IF NOT EXISTS idx_otsc_obvious
                ON obvious_trade_supply_chain(obvious_ticker);
            CREATE INDEX IF NOT EXISTS idx_otsc_supplier
                ON obvious_trade_supply_chain(supplier_ticker);
            """
        )


def record_link(
    *,
    obvious_ticker: str,
    supplier_ticker: str,
    link_strength: float,
    rationale: str | None = None,
    evidence_url: str | None = None,
) -> int:
    init()
    with db.connect() as cx:
        cur = cx.execute(
            "INSERT INTO obvious_trade_supply_chain "
            "(obvious_ticker, supplier_ticker, link_strength, rationale, evidence_url) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(obvious_ticker, supplier_ticker) DO UPDATE SET "
            "  link_strength = excluded.link_strength, "
            "  rationale = excluded.rationale, "
            "  evidence_url = excluded.evidence_url, "
            "  recorded_at = datetime('now')",
            (
                obvious_ticker.upper(),
                supplier_ticker.upper(),
                float(link_strength),
                rationale,
                evidence_url,
            ),
        )
        return int(cur.lastrowid or 0)


def import_builtin() -> int:
    n = 0
    for link in BUILTIN_LINKS:
        record_link(
            obvious_ticker=link["obvious_ticker"],
            supplier_ticker=link["supplier_ticker"],
            link_strength=link["link_strength"],
            rationale=link.get("rationale"),
        )
        n += 1
    return n


def upstream_for(obvious_ticker: str) -> list[dict]:
    """Return suppliers for ``obvious_ticker`` joined with their latest score."""
    init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT g.supplier_ticker, g.link_strength, g.rationale, "
            "       s.overall, s.scored_at, c.market_cap_usd "
            "FROM obvious_trade_supply_chain g "
            "LEFT JOIN ("
            "  SELECT ticker, overall, scored_at FROM scores "
            "  WHERE id IN (SELECT MAX(id) FROM scores GROUP BY ticker)"
            ") s ON s.ticker = g.supplier_ticker "
            "LEFT JOIN chokepoints c ON c.ticker = g.supplier_ticker "
            "WHERE g.obvious_ticker = ? "
            "ORDER BY g.link_strength DESC, g.supplier_ticker",
            (obvious_ticker.upper(),),
        ).fetchall()
        return [dict(r) for r in rows]


def downstream_for(supplier_ticker: str) -> list[dict]:
    init()
    with db.connect() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT obvious_ticker, link_strength, rationale "
            "FROM obvious_trade_supply_chain WHERE supplier_ticker = ? "
            "ORDER BY link_strength DESC",
            (supplier_ticker.upper(),),
        )]
