"""Drawdown / exit trigger monitor.

For each row in `positions`, compare last close to cost basis and high water.
Emit Telegram-ready alert lines for hard stops (-40% from cost) and the
+200% / +500% take-profit ladder defined in risk-management.md.
"""
from __future__ import annotations

from . import db


def evaluate() -> list[str]:
    db.init()
    alerts: list[str] = []
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT p.ticker, p.cost_basis, p.shares, p.high_water, p.last_price, "
            "       k.last_close "
            "FROM positions p LEFT JOIN contamination k ON p.ticker = k.ticker "
            "WHERE p.closed_at IS NULL"
        ).fetchall()
        for r in rows:
            last = r["last_price"] or r["last_close"]
            cost = r["cost_basis"]
            high = r["high_water"] or last
            if not (cost and last):
                continue
            pnl = (last - cost) / cost * 100.0
            cx.execute(
                "UPDATE positions SET last_price = ?, pnl_pct = ?, "
                "high_water = MAX(COALESCE(high_water, ?), ?) WHERE ticker = ?",
                (last, pnl, last, last, r["ticker"]),
            )
            if pnl <= -40:
                alerts.append(f"STOP {r['ticker']}: PnL {pnl:.1f}% (cost {cost:.2f} -> {last:.2f}) — close per playbook")
            elif pnl >= 500:
                alerts.append(f"TP-2 {r['ticker']}: +{pnl:.0f}% — sell 1/2, trailing stop -15%")
            elif pnl >= 200:
                alerts.append(f"TP-1 {r['ticker']}: +{pnl:.0f}% — sell 1/3, trailing stop -25%")
            elif high and last < high * 0.85:
                alerts.append(f"TRAIL {r['ticker']}: -{(1 - last/high)*100:.1f}% from high — review trailing stop")
    return alerts


def main() -> None:
    a = evaluate()
    if not a:
        print("No exit triggers.")
        return
    for line in a:
        print(line)


if __name__ == "__main__":
    main()
