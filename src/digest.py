"""Daily digest. Prints to stdout; optionally posts to Telegram.

Sections:
  1) New keyword-filtered filings (since yesterday)
  2) Top movers (5d) from contamination table
  3) Tweet cashtag spikes (most-mentioned tickers in last 24h)
  4) Current scoring snapshot per ticker
  5) Exit-trigger alerts (if any open positions)
"""
from __future__ import annotations

import datetime as dt

import requests

from . import db, drawdown, scoring
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def render_markdown() -> str:
    lines: list[str] = []
    today = dt.date.today().isoformat()
    lines.append(f"# Serenity-Killer Daily Digest -- {today}\n")

    with db.connect() as cx:
        cutoff = (dt.datetime.utcnow() - dt.timedelta(hours=36)).isoformat()
        rows = cx.execute(
            "SELECT form, title, filed_at, url, keyword_hits FROM filings "
            "WHERE discovered_at >= ? ORDER BY filed_at DESC LIMIT 50",
            (cutoff,),
        ).fetchall()
        lines.append(f"## 1) New keyword-hit filings (last 36h): {len(rows)}\n")
        for r in rows[:15]:
            lines.append(f"- [{r['form']}] {r['title']}")
            lines.append(f"  - {r['url']}")
            lines.append(f"  - hits: {r['keyword_hits']}")
        if not rows:
            lines.append("- (none)\n")

        # 2. Top movers
        movers = cx.execute(
            "SELECT ticker, last_close, pct_change_5d, pct_change_20d, "
            "       volume_ratio_20d, crowd_flag "
            "FROM contamination WHERE pct_change_5d IS NOT NULL "
            "ORDER BY ABS(pct_change_5d) DESC LIMIT 10"
        ).fetchall()
        lines.append("\n## 2) Top movers (|5d %| desc)\n")
        if movers:
            lines.append("| Ticker | Close | 5d % | 20d % | Vol ratio | Crowd |")
            lines.append("|--------|-------|------|-------|-----------|-------|")
            for m in movers:
                lines.append(
                    f"| {m['ticker']} | {m['last_close']:.2f} | "
                    f"{m['pct_change_5d']:+.1f}% | {m['pct_change_20d']:+.1f}% | "
                    f"{m['volume_ratio_20d']:.2f} | {m['crowd_flag']} |"
                )
        else:
            lines.append("- (no price data yet — run `prices`)\n")

        # 3. Tweet cashtag spikes
        cutoff_24h = (dt.datetime.utcnow() - dt.timedelta(hours=36)).isoformat()
        spikes = cx.execute(
            "SELECT tickers, COUNT(*) as c FROM tweets "
            "WHERE discovered_at >= ? AND tickers <> '' "
            "GROUP BY tickers ORDER BY c DESC LIMIT 10",
            (cutoff_24h,),
        ).fetchall()
        lines.append("\n## 3) Tweet cashtag spikes (last 36h)\n")
        if spikes:
            for s in spikes:
                lines.append(f"- {s['tickers']}: {s['c']} mentions")
        else:
            lines.append("- (no tweets ingested yet — run `tweets`)\n")

    # 4. Scoring snapshot
    lines.append("\n## 4) Scoring snapshot\n")
    lines.append("| Ticker | Overall | Step -1 | Step 1 | Step 2 | Step 8 | Step 9 |")
    lines.append("|--------|---------|---------|--------|--------|--------|--------|")
    for r in scoring.score_all():
        lines.append(
            f"| {r['ticker']} | **{r['overall']}** | {r['step_minus1']} | "
            f"{r['step_1']} | {r['step_2']} | {r['step_8']} | {r['step_9']} |"
        )

    # 5. Drawdown alerts (only if any)
    alerts = drawdown.evaluate()
    if alerts:
        lines.append("\n## 5) Exit-trigger alerts\n")
        for a in alerts:
            lines.append(f"- {a}")
    return "\n".join(lines) + "\n"


def post_to_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    # Telegram caps messages at 4096 chars; split if needed
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chunk_start in range(0, len(text), 3500):
        chunk = text[chunk_start : chunk_start + 3500]
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown", "disable_web_page_preview": "true"},
            timeout=30,
        )
        r.raise_for_status()
    return True


def main() -> None:
    md = render_markdown()
    print(md)
    sent = post_to_telegram(md)
    if sent:
        print("\n[telegram] sent.")
    else:
        print("\n[telegram] not configured (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env).")


if __name__ == "__main__":
    main()
