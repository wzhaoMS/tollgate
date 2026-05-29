"""Higher-level strategy signals from the original Serenity-Killer plan."""
from __future__ import annotations

from . import db


def true_vs_consensus(ticker: str) -> str:
    """Classify fact truth vs market consensus.

    hidden_truth => fact appears true and not yet consensus-discovered
    emerging     => fact is true but consensus is partly forming
    consensus    => fact is true but already widely known, so alpha is weaker
    unproven     => consensus may exist but truth score is not strong enough
    unknown      => no data
    """
    db.init()
    with db.connect() as cx:
        row = cx.execute(
            "SELECT truth_score, consensus_score, analyst_coverage_count, status "
            "FROM consensus_metrics WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
    if not row:
        return "unknown"
    status = (row["status"] or "unknown").lower()
    if status != "unknown":
        return status
    truth = row["truth_score"]
    consensus = row["consensus_score"]
    coverage = row["analyst_coverage_count"] or 0
    if truth is None or consensus is None:
        return "unknown"
    if truth >= 0.7 and consensus < 0.4 and coverage < 3:
        return "hidden_truth"
    if truth >= 0.7 and consensus < 0.7:
        return "emerging"
    if truth >= 0.7:
        return "consensus"
    return "unproven"


def follower_growth_pct(handle: str = "aleabitoreddit", lookback_days: int = 7) -> float | None:
    """Return follower growth over the lookback window, or None without data."""
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT follower_count FROM follower_history WHERE handle = ? "
            "AND observed_at >= datetime('now', ?) ORDER BY observed_at ASC",
            (handle, f"-{lookback_days} days"),
        ).fetchall()
    if len(rows) < 2:
        return None
    first = rows[0]["follower_count"]
    last = rows[-1]["follower_count"]
    if not first:
        return None
    return (last - first) / first * 100.0


def reverse_crowd_alerts(
    *,
    handle: str = "aleabitoreddit",
    lookback_days: int = 7,
    growth_threshold_pct: float = 15.0,
    max_market_cap_usd: float = 3_000_000_000,
) -> list[dict]:
    """Alert on recent Serenity signals when follower growth makes crowd risk high."""
    growth = follower_growth_pct(handle=handle, lookback_days=lookback_days)
    if growth is None or growth < growth_threshold_pct:
        return []
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT s.ticker, s.signaled_at, s.source_url, c.market_cap_usd "
            "FROM serenity_signals s JOIN chokepoints c ON c.ticker = s.ticker "
            "WHERE s.handle = ? AND s.signaled_at >= datetime('now', ?) "
            "AND c.market_cap_usd IS NOT NULL AND c.market_cap_usd < ? "
            "ORDER BY s.signaled_at DESC",
            (handle, f"-{lookback_days} days", max_market_cap_usd),
        ).fetchall()
    return [
        {
            "ticker": r["ticker"],
            "signaled_at": r["signaled_at"],
            "source_url": r["source_url"],
            "market_cap_usd": r["market_cap_usd"],
            "follower_growth_pct": growth,
            "signal": "reverse_watch",
        }
        for r in rows
    ]
