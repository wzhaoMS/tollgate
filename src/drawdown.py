"""Drawdown / exit trigger monitor.

For each row in `positions`, compare last close to cost basis and high water.
Emit Telegram-ready alert lines for:
  - Price-based: hard stop (-40%), take-profit ladders (+200%/+500%), trailing stop
  - Fundamental: analyst coverage surge, capacity gap closing, stale holding, M&A hold
"""
from __future__ import annotations

from . import db


def _fundamental_triggers(cx, ticker: str, cost_basis: float, opened_at: str | None) -> list[str]:
    """Check fundamental-change exit triggers for a position.

    Returns a list of alert strings (empty if no triggers fire).
    """
    alerts: list[str] = []

    # 1. Analyst coverage 0→3+ → sell 1/3 (consensus forming, alpha evaporating)
    plan = cx.execute(
        "SELECT analyst_coverage_trim_threshold, capacity_gap_exit_pct, stale_months "
        "FROM exit_plans WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    threshold = plan["analyst_coverage_trim_threshold"] if plan else 3
    fund = cx.execute("SELECT sell_side_analysts FROM fundamentals WHERE ticker = ?", (ticker,)).fetchone()
    if fund and fund["sell_side_analysts"] is not None and fund["sell_side_analysts"] >= threshold:
        alerts.append(
            f"COVERAGE {ticker}: {fund['sell_side_analysts']} analysts now covering "
            f"(threshold={threshold}) — sell 1/3, consensus forming"
        )

    # 2. Capacity gap narrowing from -25% → -5% → sell 1/2 (chokepoint fading)
    plan_gap = plan["capacity_gap_exit_pct"] if plan else -5.0
    cap = cx.execute(
        "SELECT gap_pct FROM capacity_quarterly WHERE ticker = ? ORDER BY quarter DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if not cap:
        cap = cx.execute(
            "SELECT gap_pct FROM capacity_models WHERE ticker = ? ORDER BY period DESC LIMIT 1",
            (ticker,),
        ).fetchone()
    if cap and cap["gap_pct"] is not None and cap["gap_pct"] > plan_gap:
        alerts.append(
            f"GAP-CLOSE {ticker}: capacity gap now {cap['gap_pct']:.1f}% "
            f"(exit threshold={plan_gap:.1f}%) — sell 1/2, chokepoint fading"
        )

    # 3. 18mo holding with no new catalyst → reduce 1/2
    stale_months = plan["stale_months"] if plan else 18
    if opened_at:
        age_days = cx.execute(
            "SELECT (julianday('now') - julianday(?)) AS days", (opened_at,)
        ).fetchone()
        if age_days and age_days["days"] and age_days["days"] > stale_months * 30:
            # Check for recent catalysts
            recent_cat = cx.execute(
                "SELECT COUNT(*) AS cnt FROM catalyst_events "
                "WHERE ticker = ? AND status IN ('planned','confirmed') "
                "AND event_date >= date('now', '-90 days')",
                (ticker,),
            ).fetchone()
            if not recent_cat or recent_cat["cnt"] == 0:
                alerts.append(
                    f"STALE {ticker}: held {age_days['days']:.0f} days "
                    f"({age_days['days']/30:.0f}mo) with no catalyst in 90d "
                    f"— reduce 1/2, opportunity cost"
                )

    # 4. M&A rumor confirmed → hold for premium (suppress other sells)
    ma_rumor = cx.execute(
        "SELECT COUNT(*) AS cnt FROM governance_events "
        "WHERE ticker = ? AND event_type IN ('board_appointment','ma_advisor_hire') "
        "AND prior_ma_exp = 1",
        (ticker,),
    ).fetchone()
    if ma_rumor and ma_rumor["cnt"] > 0:
        alerts.append(
            f"MA-HOLD {ticker}: {ma_rumor['cnt']} M&A governance signal(s) detected "
            f"— hold for acquisition premium, suppress partial sells"
        )

    return alerts


def evaluate() -> list[str]:
    db.init()
    alerts: list[str] = []
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT p.ticker, p.cost_basis, p.shares, p.high_water, p.last_price, "
            "       p.opened_at, k.last_close "
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
            # Price-based triggers
            if pnl <= -40:
                alerts.append(f"STOP {r['ticker']}: PnL {pnl:.1f}% (cost {cost:.2f} -> {last:.2f}) — close per playbook")
            elif pnl >= 500:
                alerts.append(f"TP-2 {r['ticker']}: +{pnl:.0f}% — sell 1/2, trailing stop -15%")
            elif pnl >= 200:
                alerts.append(f"TP-1 {r['ticker']}: +{pnl:.0f}% — sell 1/3, trailing stop -25%")
            elif high and last < high * 0.85:
                alerts.append(f"TRAIL {r['ticker']}: -{(1 - last/high)*100:.1f}% from high — review trailing stop")

            # Fundamental-change triggers
            try:
                opened_at = r["opened_at"]
            except (IndexError, KeyError):
                opened_at = None
            try:
                fund_alerts = _fundamental_triggers(cx, r["ticker"], cost, opened_at)
                alerts.extend(fund_alerts)
            except Exception:
                pass  # fundamental triggers are best-effort; don't break monitoring
    return alerts
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
