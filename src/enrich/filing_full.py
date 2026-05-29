"""Fetch the full primary filing document from EDGAR (not just the Atom feed
summary) and persist text alongside the existing `filings` row so the LLM
enricher has real text to work with."""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .. import db
from ..config import EDGAR_RPS, EDGAR_USER_AGENT
from ..scrapers.edgar import _load_keywords, _scan_keywords


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _sleep() -> None:
    if EDGAR_RPS > 0:
        time.sleep(1.0 / EDGAR_RPS)


_WS = re.compile(r"\s+")
_RFILE = re.compile(r"/r\d+\.htm[l]?$", re.I)


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return _WS.sub(" ", soup.get_text(" ", strip=True)).strip()


def _normalize_doc_href(href: str) -> str | None:
    """Return a usable document path, unwrapping the inline-XBRL viewer.

    EDGAR index pages link the primary document through the inline-XBRL
    viewer (``/ix?doc=/Archives/edgar/data/.../doc.htm``). Fetching that URL
    returns a JavaScript app shell with almost no text, so we must unwrap it
    to the raw document path.
    """
    if not href:
        return None
    if "ix?doc=" in href:
        href = href.split("ix?doc=", 1)[1]
    if "/Archives/edgar/data/" not in href:
        return None
    return href


def _resolve_primary_doc(filing_index_url: str) -> str | None:
    _sleep()
    r = requests.get(filing_index_url, headers=_headers(), timeout=30)
    if not r.ok:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    # Prefer the "Document Format Files" table whose first row is the primary doc.
    tables = soup.find_all("table", class_="tableFile")
    search_roots = tables or [soup]
    for root in search_roots:
        for a in root.select("a"):
            norm = _normalize_doc_href(a.get("href") or "")
            if not norm or not re.search(r"\.htm[l]?$", norm, re.I):
                continue
            low = norm.lower()
            if "-index.htm" in low or _RFILE.search(low) or "filingsummary" in low:
                continue
            return urljoin(filing_index_url, norm)
    # Fall back to the full submission .txt
    for a in soup.select("a"):
        norm = _normalize_doc_href(a.get("href") or "")
        if norm and re.search(r"\.txt$", norm, re.I):
            return urljoin(filing_index_url, norm)
    return None


def fetch_one(accession_no: str, max_chars: int = 60_000) -> int:
    """Return # chars stored; 0 if we couldn't fetch a body.

    Also re-scans the *full body* against the keyword dictionary and refreshes
    the filing's ``keyword_hits`` column. The harvest-time scan only saw the
    thin Atom headline; the real CHIPS/DoE/supplier language lives in the body,
    so this is where deterministic evidence actually gets flagged.
    """
    db.init()
    kw = _load_keywords()
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
        full_text = _clean_html(r.text)
        # Scan the *entire* body for keywords (CHIPS/DoE language often sits
        # deep in 10-K risk factors), but only persist a truncated copy.
        hits = _scan_keywords(full_text, kw) if kw else []
        stored = full_text[:max_chars]
        cx.execute(
            "UPDATE filings SET summary = ?, keyword_hits = ? WHERE accession_no = ?",
            (stored, ",".join(hits), accession_no),
        )
        return len(stored)


def fetch_recent(limit: int = 25, forms: tuple[str, ...] | None = ("8-K",)) -> dict:
    """Fetch primary-document bodies for filings lacking real text.

    Defaults to 8-K filings, which is where government awards, supply
    agreements, and other catalysts are announced. Pass ``forms=None`` to
    process every form type.
    """
    db.init()
    results = {"fetched": 0, "skipped": 0, "errors": 0, "govt": 0}
    with db.connect() as cx:
        sql = (
            "SELECT accession_no FROM filings "
            "WHERE (summary IS NULL OR length(summary) < 500) "
        )
        params: list = []
        if forms:
            sql += f"AND form IN ({','.join('?' for _ in forms)}) "
            params.extend(forms)
        sql += "ORDER BY filed_at DESC, discovered_at DESC LIMIT ?"
        params.append(limit)
        rows = cx.execute(sql, params).fetchall()
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
    with db.connect() as cx:
        results["govt"] = cx.execute(
            "SELECT COUNT(*) FROM filings WHERE keyword_hits LIKE '%govt_backstop%'"
        ).fetchone()[0]
    return results


def main() -> None:
    res = fetch_recent()
    print(
        f"filing-text fetch: +{res['fetched']} full docs, "
        f"skipped={res['skipped']}, errors={res['errors']}, "
        f"govt-flagged filings now={res['govt']}"
    )


if __name__ == "__main__":
    main()
