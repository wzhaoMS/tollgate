"""Fetch the full primary filing document from EDGAR (not just the Atom feed
summary) and persist text alongside the existing `filings` row so the LLM
enricher has real text to work with."""
from __future__ import annotations
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..config import EDGAR_RPS, EDGAR_USER_AGENT
from .. import db


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _sleep() -> None:
    if EDGAR_RPS > 0:
        time.sleep(1.0 / EDGAR_RPS)


_WS = re.compile(r"\s+")


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return _WS.sub(" ", soup.get_text(" ", strip=True)).strip()


def _resolve_primary_doc(filing_index_url: str) -> str | None:
    _sleep()
    r = requests.get(filing_index_url, headers=_headers(), timeout=30)
    if not r.ok:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.select("a"):
        href = a.get("href") or ""
        # primary form HTM/HTML or txt
        if re.search(r"\.htm[l]?$", href, re.I) and "/Archives/edgar/data/" in href:
            return urljoin(filing_index_url, href)
    for a in soup.select("a"):
        href = a.get("href") or ""
        if re.search(r"\.txt$", href, re.I) and "/Archives/edgar/data/" in href:
            return urljoin(filing_index_url, href)
    return None


def fetch_one(accession_no: str, max_chars: int = 60_000) -> int:
    """Return # chars stored; 0 if we couldn't fetch a body."""
    db.init()
    with db.connect() as cx:
        row = cx.execute(
            "SELECT accession_no, url, summary FROM filings WHERE accession_no = ?",
            (accession_no,),
        ).fetchone()
        if not row:
            return 0
        body_url = _resolve_primary_doc(row["url"])
        if not body_url:
            return 0
        _sleep()
        r = requests.get(body_url, headers=_headers(), timeout=45)
        if not r.ok:
            return 0
        text = _clean_html(r.text)[:max_chars]
        cx.execute(
            "UPDATE filings SET summary = ? WHERE accession_no = ?",
            (text, accession_no),
        )
        return len(text)


def fetch_recent(limit: int = 25) -> dict:
    db.init()
    results = {"fetched": 0, "skipped": 0, "errors": 0}
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT accession_no FROM filings "
            "WHERE (summary IS NULL OR length(summary) < 500) "
            "ORDER BY discovered_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    for r in rows:
        try:
            n = fetch_one(r["accession_no"])
            if n > 0:
                results["fetched"] += 1
            else:
                results["skipped"] += 1
        except Exception as e:  # noqa: BLE001
            print(f"  fetch err {r['accession_no']}: {e}")
            results["errors"] += 1
    return results


def main() -> None:
    res = fetch_recent()
    print(
        f"filing-text fetch: +{res['fetched']} full docs, "
        f"skipped={res['skipped']}, errors={res['errors']}"
    )


if __name__ == "__main__":
    main()
