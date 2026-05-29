"""Persisted exit plans based on the original playbook rules."""
from __future__ import annotations

from . import db


def ensure_default(ticker: str, notes: str | None = None) -> dict:
    """Create a default exit plan if missing and return it."""
    db.init()
    with db.connect() as cx:
        cx.execute(
            "INSERT OR IGNORE INTO exit_plans (ticker, notes) VALUES (?, ?)",
            (ticker.upper(), notes),
        )
        row = cx.execute("SELECT * FROM exit_plans WHERE ticker = ?", (ticker.upper(),)).fetchone()
        return dict(row)


def missing_exit_plans() -> list[str]:
    """Return open position tickers without a persisted exit plan."""
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT p.ticker FROM positions p LEFT JOIN exit_plans e ON e.ticker = p.ticker "
            "WHERE p.closed_at IS NULL AND e.ticker IS NULL ORDER BY p.ticker"
        ).fetchall()
    return [r["ticker"] for r in rows]


def ensure_for_open_positions() -> int:
    created = 0
    for ticker in missing_exit_plans():
        ensure_default(ticker, notes="auto-created for open position")
        created += 1
    return created
