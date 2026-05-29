"""Weekly brief: summarize the week's filings + tweets + scoring deltas using
the local Claude bridge.

Usage:
  py -m src.brief        # print to stdout
"""
from __future__ import annotations

import datetime as dt

from . import db
from .bridge_client import chat


def _gather(cx, days: int = 7) -> dict:
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat()
    filings = cx.execute(
        "SELECT form, title, filed_at, keyword_hits FROM filings "
        "WHERE discovered_at >= ? ORDER BY filed_at DESC LIMIT 40",
        (cutoff,),
    ).fetchall()
    tweets = cx.execute(
        "SELECT handle, posted_at, tickers, text FROM tweets "
        "WHERE discovered_at >= ? AND tickers <> '' ORDER BY posted_at DESC LIMIT 60",
        (cutoff,),
    ).fetchall()
    movers = cx.execute(
        "SELECT ticker, last_close, pct_change_5d, pct_change_20d, "
        "       volume_ratio_20d, crowd_flag "
        "FROM contamination WHERE pct_change_5d IS NOT NULL "
        "ORDER BY ABS(pct_change_5d) DESC LIMIT 15"
    ).fetchall()
    scores = cx.execute(
        "SELECT ticker, overall, scored_at FROM scores "
        "WHERE id IN (SELECT MAX(id) FROM scores GROUP BY ticker)"
    ).fetchall()
    return {
        "filings": [dict(r) for r in filings],
        "tweets": [dict(r) for r in tweets],
        "movers": [dict(r) for r in movers],
        "scores": [dict(r) for r in scores],
    }


_SYSTEM = (
    "You are a hedge-fund analyst writing a tight weekly note for a chokepoint / "
    "supply-chain OSINT pipeline. Be concise. Use the Serenity-Killer playbook "
    "framework (Step -1 to Step 11). Cite specific tickers and concrete numbers. "
    "Do not invent data not present in the input."
)


def build_prompt(payload: dict) -> str:
    parts = [
        "# This week's data dump\n",
        "## Filings (keyword-hit)",
    ]
    for f in payload["filings"][:25]:
        parts.append(f"- [{f['form']}] {f['title']} — hits: {f['keyword_hits']}")
    parts.append("\n## Tweets with cashtags")
    for t in payload["tweets"][:30]:
        parts.append(f"- @{t['handle']} ({t['posted_at']}): {t['tickers']} — {t['text'][:140]}")
    parts.append("\n## Top movers (price/volume)")
    for m in payload["movers"]:
        parts.append(
            f"- {m['ticker']}: close {m['last_close']:.2f}, "
            f"5d {m['pct_change_5d']:+.1f}%, 20d {m['pct_change_20d']:+.1f}%, "
            f"volR {m['volume_ratio_20d']:.2f}, crowd={m['crowd_flag']}"
        )
    parts.append("\n## Current scoring")
    for s in payload["scores"]:
        parts.append(f"- {s['ticker']}: {s['overall']}")
    parts.append(
        "\n# Task\n"
        "Write a structured weekly brief with these sections:\n"
        "1. Top 3 *evidence upgrades* (filings that move a ticker grade up the A/B/C/D ladder)\n"
        "2. Top 3 *contamination warnings* (tickers where price/tweet momentum suggests we are late)\n"
        "3. Pair-trade ideas justified by the data above\n"
        "4. Concrete next steps for the operator this week (max 5 bullets)\n"
        "Keep it under 600 words."
    )
    return "\n".join(parts)


def main() -> None:
    db.init()
    with db.connect() as cx:
        payload = _gather(cx)
    prompt = build_prompt(payload)
    out = chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        timeout=180,
    )
    # Windows console default cp1252 can't render Claude's unicode arrows etc.
    # Write through stdout buffer in utf-8 with a safe fallback.
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(out)
    except Exception:
        print(out.encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    main()
