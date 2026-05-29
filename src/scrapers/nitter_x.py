"""X/Twitter scraping via Nitter mirrors.

Nitter instances rotate availability. We try a list of mirrors, parse the user
timeline RSS, persist new tweets, and extract `$TICKER` cashtags via a regex
intersected with our chokepoints universe.
"""
from __future__ import annotations
import re
import time
from typing import Iterable

import feedparser
import requests

from ..config import EDGAR_USER_AGENT  # reuse the polite UA
from .. import db

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.kavin.rocks",
    "https://nitter.tiekoetter.com",
]

# Seed handle list (subset; the full curated list lives in data/handles.json once written)
DEFAULT_HANDLES = [
    "aleabitoreddit",  # Serenity
    "leopoldasch",
    "dylan522p",
    "Jukanlosreve",
    "SKundojjala",
    "doug_oloughlin",
    "mule_capital",
    "AyarLabs",
    "lightmatterco",
    "AsteraLabs",
    "MarvellTech",
    "Broadcom",
    "nvidia",
    "TrendForce_",
    "semiengineering",
    "TheValueist",
    "0xKevin00",
    "ai_9684xtpa",
    "schwerelos",
]


_CASHTAG = re.compile(r"\$([A-Z][A-Z0-9.\-]{0,5})\b")


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_USER_AGENT, "Accept": "application/rss+xml"}


def _try_fetch(handle: str) -> bytes | None:
    last_err: Exception | None = None
    for base in NITTER_INSTANCES:
        url = f"{base}/{handle}/rss"
        try:
            r = requests.get(url, headers=_headers(), timeout=15)
            if r.ok and (b"<rss" in r.content[:200].lower() or b"<feed" in r.content[:200].lower()):
                return r.content
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    if last_err:
        print(f"  [nitter] {handle}: all mirrors failed ({last_err})")
    return None


def fetch_handle(handle: str, universe: set[str] | None = None) -> int:
    body = _try_fetch(handle)
    if not body:
        return 0
    parsed = feedparser.parse(body)
    inserted = 0
    with db.connect() as cx:
        for entry in parsed.entries[:50]:
            link = entry.get("link") or ""
            tid = link.rstrip("/").split("/")[-1] or entry.get("id") or link
            text = entry.get("title") or entry.get("summary") or ""
            posted = entry.get("published") or entry.get("updated") or ""
            tags = sorted({m.group(1).upper() for m in _CASHTAG.finditer(text)})
            if universe is not None:
                tags = [t for t in tags if t in universe]
            cur = cx.execute(
                "INSERT OR IGNORE INTO tweets (tweet_id, handle, posted_at, text, tickers, url) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tid, handle, posted, text, ",".join(tags), link),
            )
            if cur.rowcount:
                inserted += 1
    return inserted


def harvest_handles(handles: Iterable[str] = DEFAULT_HANDLES) -> int:
    db.init()
    with db.connect() as cx:
        universe = {r[0] for r in cx.execute("SELECT ticker FROM chokepoints")}
    total = 0
    for h in handles:
        try:
            n = fetch_handle(h, universe=universe)
            total += n
            print(f"  {h}: +{n} new tweets")
            time.sleep(1.2)  # polite to nitter
        except Exception as e:  # noqa: BLE001
            print(f"  [nitter err] {h}: {e}")
    return total


def main() -> None:
    n = harvest_handles()
    print(f"Inserted {n} new tweets total.")


if __name__ == "__main__":
    main()
