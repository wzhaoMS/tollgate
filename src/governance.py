"""Governance events — board changes, M&A advisor hires, director backgrounds.

Tracks signals like "new board members with M&A experience" that Serenity
uses as acquisition indicators.
"""
from __future__ import annotations

from typing import Any

from . import db

# Builtin governance events from known filings / annual reports
BUILTIN_EVENTS: list[dict[str, Any]] = [
    {
        "ticker": "SIVE",
        "event_type": "board_appointment",
        "person_name": "New M&A Director",
        "role": "Board Member",
        "prior_ma_exp": 1,
        "source_url": "https://www.sivers-semiconductors.com/annual-report-2025",
        "event_date": "2025-03-15",
        "notes": "2025 AR mentions 'new board members with M&A experience' — Serenity flag",
    },
    {
        "ticker": "XFAB",
        "event_type": "govt_designation",
        "person_name": None,
        "role": None,
        "prior_ma_exp": 0,
        "source_url": "https://www.nist.gov/chips",
        "event_date": "2024-06-01",
        "notes": "NIST/Dept of Commerce designation as 'sole high-volume US SiC foundry'",
    },
    {
        "ticker": "AXTI",
        "event_type": "capacity_announcement",
        "person_name": None,
        "role": None,
        "prior_ma_exp": 0,
        "source_url": None,
        "event_date": "2025-01-20",
        "notes": "New InP crystal growth furnaces announced; 12-18mo lead time",
    },
]


def import_builtin_events() -> int:
    """Seed builtin governance events. Returns rows inserted."""
    db.init()
    inserted = 0
    with db.connect() as cx:
        for ev in BUILTIN_EVENTS:
            try:
                cx.execute(
                    "INSERT INTO governance_events "
                    "(ticker, event_type, person_name, role, prior_ma_exp, "
                    " source_url, event_date, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ev["ticker"], ev["event_type"], ev["person_name"],
                        ev["role"], ev["prior_ma_exp"], ev["source_url"],
                        ev["event_date"], ev["notes"],
                    ),
                )
                if cx.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except Exception:
                continue
    return inserted


def ma_signals(ticker: str | None = None) -> list[dict[str, Any]]:
    """Return governance events that signal M&A activity.

    If ticker is None, returns all M&A-relevant events.
    """
    db.init()
    with db.connect() as cx:
        if ticker:
            rows = cx.execute(
                "SELECT * FROM governance_events "
                "WHERE ticker = ? AND (prior_ma_exp = 1 OR event_type = 'board_appointment') "
                "ORDER BY event_date DESC",
                (ticker.upper(),),
            ).fetchall()
        else:
            rows = cx.execute(
                "SELECT * FROM governance_events "
                "WHERE prior_ma_exp = 1 OR event_type = 'board_appointment' "
                "ORDER BY event_date DESC",
            ).fetchall()
        return [dict(r) for r in rows]


def recent_events(ticker: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent governance events, optionally filtered by ticker."""
    db.init()
    with db.connect() as cx:
        if ticker:
            rows = cx.execute(
                "SELECT * FROM governance_events WHERE ticker = ? "
                "ORDER BY discovered_at DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        else:
            rows = cx.execute(
                "SELECT * FROM governance_events "
                "ORDER BY discovered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
