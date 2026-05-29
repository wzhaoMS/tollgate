"""Pair-trade candidate generator.

For each ticker tagged into a `theme`, pair it with the same-theme peer that has
the highest 20-day price appreciation (likely over-extended). Long the lower
20d performer; short the higher 20d performer; size 50/50.

We define theme implicitly from the `chokepoint` text column (rough but enough
for v0). A future version reads from a tagged taxonomy.
"""
from __future__ import annotations

from . import db


def hedge_notional(gross_notional: float) -> dict[str, float]:
    """Return equal-dollar long/short notionals for a beta-reduced pair."""
    half = max(0.0, float(gross_notional)) / 2.0
    return {"long_notional": half, "short_notional": half, "gross_notional": half * 2.0}


def _theme_of(chokepoint: str | None) -> str:
    s = (chokepoint or "").lower()
    if any(k in s for k in ["laser", "elsfp", "external light", "cw laser"]):
        return "external_light"
    if any(k in s for k in ["sic", "silicon-photonics foundry", "foundry"]):
        return "sic_foundry"
    if any(k in s for k in ["inp", "indium phosphide", "substrate"]):
        return "inp_substrate"
    if any(k in s for k in ["soi", "silicon photonics"]):
        return "sip"
    if any(k in s for k in ["optical", "transceiver", "dci", "photonics"]):
        return "optical_transport"
    return "other"


def candidates() -> list[dict]:
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT c.ticker, c.chokepoint, c.market_cap_usd, "
            "       k.pct_change_20d, k.crowd_flag "
            "FROM chokepoints c LEFT JOIN contamination k ON c.ticker = k.ticker"
        ).fetchall()
    by_theme: dict[str, list[dict]] = {}
    for r in rows:
        d = {
            "ticker": r["ticker"],
            "theme": _theme_of(r["chokepoint"]),
            "market_cap": r["market_cap_usd"],
            "pct_20d": r["pct_change_20d"],
            "crowd": r["crowd_flag"],
        }
        by_theme.setdefault(d["theme"], []).append(d)

    pairs: list[dict] = []
    for theme, members in by_theme.items():
        members = [m for m in members if m["pct_20d"] is not None]
        if len(members) < 2:
            continue
        members.sort(key=lambda x: x["pct_20d"])
        long = members[0]
        short = members[-1]
        if long["ticker"] == short["ticker"]:
            continue
        pairs.append(
            {
                "theme": theme,
                "long": long["ticker"],
                "long_20d": long["pct_20d"],
                "short": short["ticker"],
                "short_20d": short["pct_20d"],
                "spread_pct": short["pct_20d"] - long["pct_20d"],
            }
        )
    pairs.sort(key=lambda p: p["spread_pct"], reverse=True)
    return pairs


def sync_watchlist(limit: int | None = None) -> int:
    """Persist current pair candidates into the open watchlist.

    Existing open long/short pairs are left untouched. Returns number of new
    watchlist rows inserted.
    """
    inserted = 0
    picks = candidates()
    if limit is not None:
        picks = picks[:limit]
    with db.connect() as cx:
        for pair in picks:
            cur = cx.execute(
                "INSERT INTO pair_trade_watchlist "
                "(theme, long_ticker, short_ticker, entry_spread_pct, current_spread_pct) "
                "SELECT ?, ?, ?, ?, ? "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM pair_trade_watchlist "
                "  WHERE closed_at IS NULL AND long_ticker = ? AND short_ticker = ?"
                ")",
                (
                    pair["theme"],
                    pair["long"],
                    pair["short"],
                    pair["spread_pct"],
                    pair["spread_pct"],
                    pair["long"],
                    pair["short"],
                ),
            )
            inserted += cur.rowcount or 0
    return inserted


def record_snapshots() -> int:
    """Record price snapshots and pair P&L for open watchlist rows."""
    db.init()
    inserted = 0
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT id, long_ticker, short_ticker FROM pair_trade_watchlist WHERE closed_at IS NULL"
        ).fetchall()
        for pair in rows:
            prices = cx.execute(
                "SELECT ticker, last_close FROM contamination "
                "WHERE ticker IN (?, ?) AND last_close IS NOT NULL",
                (pair["long_ticker"], pair["short_ticker"]),
            ).fetchall()
            by_ticker = {r["ticker"]: float(r["last_close"]) for r in prices}
            long_price = by_ticker.get(pair["long_ticker"])
            short_price = by_ticker.get(pair["short_ticker"])
            if not long_price or not short_price:
                continue
            prev = cx.execute(
                "SELECT long_price, short_price FROM pair_trade_snapshots "
                "WHERE watchlist_id = ? ORDER BY measured_at ASC, id ASC LIMIT 1",
                (pair["id"],),
            ).fetchone()
            if prev and prev["long_price"] and prev["short_price"]:
                long_ret = (long_price - prev["long_price"]) / prev["long_price"] * 100.0
                short_ret = (prev["short_price"] - short_price) / prev["short_price"] * 100.0
                pnl_pct = (long_ret + short_ret) / 2.0
            else:
                pnl_pct = 0.0
            spread_pct = ((short_price / long_price) - 1.0) * 100.0
            cx.execute(
                "INSERT INTO pair_trade_snapshots "
                "(watchlist_id, long_price, short_price, spread_pct, pnl_pct) "
                "VALUES (?, ?, ?, ?, ?)",
                (pair["id"], long_price, short_price, spread_pct, pnl_pct),
            )
            cx.execute(
                "UPDATE pair_trade_watchlist SET current_spread_pct = ? WHERE id = ?",
                (spread_pct, pair["id"]),
            )
            inserted += 1
    return inserted


def main() -> None:
    for p in candidates():
        print(
            f"  [{p['theme']}] LONG {p['long']} ({p['long_20d']:.1f}%) / "
            f"SHORT {p['short']} ({p['short_20d']:.1f}%) spread={p['spread_pct']:.1f}%"
        )


if __name__ == "__main__":
    main()
