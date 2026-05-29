"""Seeders for tables that depend on curated/manual data:

- ``serenity_signals``: her tweets with ticker / signal timestamp.
- ``follower_history``: smart-money handle follower counts over time.
- ``govt_awards``: official CHIPS Act / DoE / EU awards with funding amounts.

We provide CSV loaders + a small built-in CHIPS Act seed so step 4
(government backstop) has real data without waiting for external feeds.

CSV formats (UTF-8, header rows required)
-----------------------------------------

``serenity_signals.csv``::

    ticker,handle,tweet_id,signaled_at,source_url,signal_text,price_at_signal,follower_count

``follower_history.csv``::

    handle,observed_at,follower_count,source_url

``govt_awards.csv``::

    ticker,agency,program,award_amount_usd,official_url,announced_at,source_excerpt
"""
from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from . import db
from .config import DATA_DIR

SEED_DIR = DATA_DIR / "seeds"


# ---------------------------------------------------------------------------
# Built-in CHIPS Act / DoE awards seed (public chips.gov / commerce.gov data).
# Amounts in USD. Use ``seed_govt --builtin`` to load this.
# ---------------------------------------------------------------------------
BUILTIN_GOVT_AWARDS: list[dict] = [
    {
        "ticker": "XFAB",
        "agency": "U.S. Department of Commerce",
        "program": "CHIPS and Science Act",
        "award_amount_usd": 50_000_000,
        "official_url": "https://www.commerce.gov/news/press-releases",
        "announced_at": "2024-12-01",
        "source_excerpt": "X-FAB Texas selected for CHIPS funding to expand U.S. SiC capacity.",
    },
    {
        "ticker": "WOLF",
        "agency": "U.S. Department of Commerce",
        "program": "CHIPS and Science Act",
        "award_amount_usd": 750_000_000,
        "official_url": "https://www.commerce.gov/news/press-releases",
        "announced_at": "2024-10-01",
        "source_excerpt": "Wolfspeed proposed direct funding for SiC wafer expansion (Mohawk Valley, NC).",
    },
    {
        "ticker": "GFS",
        "agency": "U.S. Department of Commerce",
        "program": "CHIPS and Science Act",
        "award_amount_usd": 1_500_000_000,
        "official_url": "https://www.commerce.gov/news/press-releases",
        "announced_at": "2024-02-19",
        "source_excerpt": "GlobalFoundries direct funding for Malta NY + Burlington VT expansions.",
    },
    {
        "ticker": "INTC",
        "agency": "U.S. Department of Commerce",
        "program": "CHIPS and Science Act",
        "award_amount_usd": 8_500_000_000,
        "official_url": "https://www.commerce.gov/news/press-releases",
        "announced_at": "2024-03-20",
        "source_excerpt": "Intel direct funding for AZ/OH/NM/OR commercial fab expansions.",
    },
    {
        "ticker": "MU",
        "agency": "U.S. Department of Commerce",
        "program": "CHIPS and Science Act",
        "award_amount_usd": 6_140_000_000,
        "official_url": "https://www.commerce.gov/news/press-releases",
        "announced_at": "2024-04-25",
        "source_excerpt": "Micron direct funding for NY/ID DRAM fabs.",
    },
    {
        "ticker": "TSM",
        "agency": "U.S. Department of Commerce",
        "program": "CHIPS and Science Act",
        "award_amount_usd": 6_600_000_000,
        "official_url": "https://www.commerce.gov/news/press-releases",
        "announced_at": "2024-04-08",
        "source_excerpt": "TSMC Arizona direct funding for advanced node fabs.",
    },
]


def _rows_from_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [{k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()} for row in csv.DictReader(fh)]


def import_serenity_signals(path: Path | None = None) -> int:
    """Insert rows from a CSV; returns inserted-row count. Idempotent on
    (handle, tweet_id) UNIQUE."""
    path = Path(path or SEED_DIR / "serenity_signals.csv")
    if not path.exists():
        return 0
    rows = _rows_from_csv(path)
    db.init()
    inserted = 0
    with db.connect() as cx:
        for r in rows:
            cur = cx.execute(
                "INSERT OR IGNORE INTO serenity_signals "
                "(ticker, handle, tweet_id, signaled_at, source_url, signal_text, "
                " price_at_signal, follower_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (r.get("ticker") or "").upper(),
                    r.get("handle") or "aleabitoreddit",
                    r.get("tweet_id") or None,
                    r.get("signaled_at") or None,
                    r.get("source_url") or None,
                    r.get("signal_text") or None,
                    float(r["price_at_signal"]) if r.get("price_at_signal") else None,
                    int(r["follower_count"]) if r.get("follower_count") else None,
                ),
            )
            inserted += cur.rowcount or 0
    return inserted


def import_follower_history(path: Path | None = None) -> int:
    path = Path(path or SEED_DIR / "follower_history.csv")
    if not path.exists():
        return 0
    rows = _rows_from_csv(path)
    db.init()
    inserted = 0
    with db.connect() as cx:
        for r in rows:
            cur = cx.execute(
                "INSERT OR IGNORE INTO follower_history "
                "(handle, observed_at, follower_count, source_url) VALUES (?, ?, ?, ?)",
                (
                    r.get("handle"),
                    r.get("observed_at"),
                    int(r["follower_count"]) if r.get("follower_count") else 0,
                    r.get("source_url") or None,
                ),
            )
            inserted += cur.rowcount or 0
    return inserted


def import_govt_awards(
    path: Path | None = None,
    rows: Iterable[dict] | None = None,
) -> int:
    """Insert from explicit ``rows``, a CSV ``path``, or the built-in seed.

    De-dupes on (ticker, agency, announced_at, award_amount_usd).
    """
    if rows is None:
        if path is None:
            return 0
        path = Path(path)
        if not path.exists():
            return 0
        rows = _rows_from_csv(path)
    db.init()
    inserted = 0
    with db.connect() as cx:
        for r in rows:
            existing = cx.execute(
                "SELECT 1 FROM govt_awards WHERE ticker = ? AND IFNULL(agency,'') = IFNULL(?, '') "
                "AND IFNULL(announced_at,'') = IFNULL(?, '') AND IFNULL(award_amount_usd, 0) = ?",
                (
                    (r.get("ticker") or "").upper(),
                    r.get("agency"),
                    r.get("announced_at"),
                    float(r.get("award_amount_usd") or 0),
                ),
            ).fetchone()
            if existing:
                continue
            cx.execute(
                "INSERT INTO govt_awards "
                "(ticker, agency, program, award_amount_usd, official_url, announced_at, source_excerpt) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    (r.get("ticker") or "").upper(),
                    r.get("agency"),
                    r.get("program"),
                    float(r["award_amount_usd"]) if r.get("award_amount_usd") else None,
                    r.get("official_url"),
                    r.get("announced_at"),
                    r.get("source_excerpt"),
                ),
            )
            inserted += 1
    return inserted


def import_builtin_govt() -> int:
    return import_govt_awards(rows=BUILTIN_GOVT_AWARDS)
