"""Daily digest. Prints to stdout; optionally posts to Telegram.

Sections:
  1) New keyword-filtered filings (since yesterday)
  2) Current scoring snapshot per ticker
"""
from __future__ import annotations
import datetime as dt
import requests
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from . import db, scoring


def render_markdown() -> str:
    lines: list[str] = []
    today = dt.date.today().isoformat()
    lines.append(f"# Serenity-Killer Daily Digest — {today}\n")

    # 1. Recent filings
    with db.connect() as cx:
        cutoff = (dt.datetime.utcnow() - dt.timedelta(hours=36)).isoformat()
        rows = cx.execute(
            "SELECT form, title, filed_at, url, keyword_hits FROM filings "
            "WHERE discovered_at >= ? ORDER BY filed_at DESC LIMIT 50",
            (cutoff,),
        ).fetchall()
    lines.append(f"## New keyword-hit filings (last 36h): {len(rows)}\n")
    for r in rows[:25]:
        lines.append(f"- [{r['form']}] {r['title']}")
        lines.append(f"  - {r['url']}")
        lines.append(f"  - hits: {r['keyword_hits']}")
    if not rows:
        lines.append("- (none)\n")

    # 2. Scoring snapshot
    lines.append("\n## Scoring snapshot\n")
    lines.append("| Ticker | Overall | Step -1 | Step 1 | Step 8 | Step 9 |")
    lines.append("|--------|---------|---------|--------|--------|--------|")
    for r in scoring.score_all():
        lines.append(
            f"| {r['ticker']} | {r['overall']} | {r['step_minus1']} | {r['step_1']} | {r['step_8']} | {r['step_9']} |"
        )
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
