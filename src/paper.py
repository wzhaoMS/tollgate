"""Tiny paper-trading wrapper.

No external broker required. Lets you record paper positions in the same DB
and reuse the drawdown monitor. Connect to Alpaca later by swapping `place_order`.
"""
from __future__ import annotations
from . import db


def open_position(ticker: str, shares: float, cost_basis: float, notes: str = "") -> None:
    db.init()
    with db.connect() as cx:
        cx.execute(
            "INSERT OR REPLACE INTO positions "
            "(ticker, cost_basis, shares, high_water, last_price, pnl_pct, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker.upper(), cost_basis, shares, cost_basis, cost_basis, 0.0, notes),
        )


def close_position(ticker: str) -> None:
    db.init()
    with db.connect() as cx:
        cx.execute(
            "UPDATE positions SET closed_at = datetime('now') WHERE ticker = ?",
            (ticker.upper(),),
        )


def list_positions() -> list[dict]:
    db.init()
    with db.connect() as cx:
        return [dict(r) for r in cx.execute(
            "SELECT * FROM positions WHERE closed_at IS NULL ORDER BY ticker"
        )]


def main() -> None:
    for p in list_positions():
        print(p)


if __name__ == "__main__":
    main()
