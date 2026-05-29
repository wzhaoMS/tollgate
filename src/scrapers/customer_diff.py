"""Lightweight customer-website diff (Visualping replacement, no headless browser).

Hashes cleaned HTML, persists a snapshot per URL, flags changes between runs.
For richer JS-rendered pages this is a coarse approximation, but for static
"partners" / "suppliers" pages on company websites it's enough.
"""
from __future__ import annotations
import hashlib
import re
import time

import requests
from bs4 import BeautifulSoup

from ..config import EDGAR_USER_AGENT
from .. import db

WATCH_URLS = [
    "https://ayarlabs.com",
    "https://lightmatter.co/about/",
    "https://celestial.ai",
    "https://www.astera.com",
    "https://www.nvidia.com/en-us/partners/",
    "https://www.broadcom.com/solutions/data-center",
    "https://www.marvell.com/solutions/data-center.html",
    "https://wiwynn.com/solution/ai-computing-solution/",
    "https://www.alchip.com/en/Business_Models/model",
    "https://azure.microsoft.com/en-us/solutions/artificial-intelligence/",
    "https://aws.amazon.com/ai/",
    "https://cloud.google.com/ai",
    "https://www.ciena.com/solutions/",
    "https://www.arista.com/en/company/customers",
]


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "no-cache",
    }


_WS = re.compile(r"\s+")
_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


def _clean(html: str) -> str:
    """Drop <script>/<style>, then extract text only and collapse whitespace."""
    html = _TAGS.sub(" ", html)
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return _WS.sub(" ", text).strip()


def snapshot(url: str) -> dict | None:
    try:
        r = requests.get(url, headers=_headers(), timeout=25)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"  [diff err] {url}: {e}")
        return None
    cleaned = _clean(r.text)
    sha = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    char_len = len(cleaned)
    with db.connect() as cx:
        prev = cx.execute(
            "SELECT content_sha256, char_len FROM page_snapshots WHERE url = ? "
            "ORDER BY snapshot_at DESC LIMIT 1",
            (url,),
        ).fetchone()
        changed = (prev is None) or (prev["content_sha256"] != sha)
        diff_lines = abs(char_len - (prev["char_len"] if prev else 0))
        cx.execute(
            "INSERT INTO page_snapshots (url, content_sha256, char_len, diff_lines) "
            "VALUES (?, ?, ?, ?)",
            (url, sha, char_len, diff_lines),
        )
    return {"url": url, "changed": changed, "char_len": char_len, "diff_chars": diff_lines}


def snapshot_all(urls: list[str] | None = None) -> list[dict]:
    db.init()
    results: list[dict] = []
    for url in urls or WATCH_URLS:
        r = snapshot(url)
        if r:
            results.append(r)
            marker = "*" if r["changed"] else " "
            print(f"  {marker} {url} ({r['char_len']} chars; delta={r['diff_chars']})")
        time.sleep(0.8)  # polite
    changed = [r for r in results if r["changed"]]
    print(f"Snapshotted {len(results)} URLs ({len(changed)} changed).")
    return results


def main() -> None:
    snapshot_all()


if __name__ == "__main__":
    main()
