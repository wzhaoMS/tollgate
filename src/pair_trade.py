"""Pair-trade candidate generator.

For each ticker tagged into a `theme`, pair it with the same-theme peer that has
the highest 20-day price appreciation (likely over-extended). Long the lower
20d performer; short the higher 20d performer; size 50/50.

We define theme implicitly from the `chokepoint` text column (rough but enough
for v0). A future version reads from a tagged taxonomy.
"""
from __future__ import annotations

from . import db


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


def main() -> None:
    for p in candidates():
        print(
            f"  [{p['theme']}] LONG {p['long']} ({p['long_20d']:.1f}%) / "
            f"SHORT {p['short']} ({p['short_20d']:.1f}%) spread={p['spread_pct']:.1f}%"
        )


if __name__ == "__main__":
    main()
