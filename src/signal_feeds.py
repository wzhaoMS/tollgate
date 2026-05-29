"""Signal-feed monitoring: EDGAR RSS, Federal Register, customer page diffs.

This module provides automated keyword-filtered alerts from public data
sources. Alerts are persisted to `signal_feed_alerts` for dashboard display
and CLI triage.
"""
from __future__ import annotations

import hashlib
import re
import urllib.request
from datetime import UTC, datetime
from typing import Any

from . import db
from .config import EDGAR_USER_AGENT

# ─── keyword sets ────────────────────────────────────────────────────────────
SOLE_SOURCE_KEYWORDS: list[str] = [
    "sole source",
    "single source",
    "sole supplier",
    "primary supplier",
    "critical material",
    "key supplier",
    "sole provider",
    "exclusively supplied",
    "dependent on",
    "single-source",
]

GOVT_KEYWORDS: list[str] = [
    "CHIPS Act",
    "CHIPS and Science",
    "Department of Commerce",
    "National Institute of Standards",
    "NIST",
    "critical infrastructure",
    "semiconductor incentive",
    "EU Chips Act",
    "European Chips Act",
]

# Tickers of interest (loaded from DB at runtime when available)
_TRACKED_TICKERS: list[str] | None = None


def _tracked_tickers() -> list[str]:
    global _TRACKED_TICKERS
    if _TRACKED_TICKERS is not None:
        return _TRACKED_TICKERS
    try:
        db.init()
        with db.connect() as cx:
            rows = cx.execute("SELECT ticker FROM chokepoints ORDER BY ticker").fetchall()
            _TRACKED_TICKERS = [r["ticker"] for r in rows]
    except Exception:
        _TRACKED_TICKERS = []
    return _TRACKED_TICKERS


def _safe_get(url: str, *, timeout: int = 30) -> str:
    """Fetch URL with proper User-Agent, return text or empty on error."""
    req = urllib.request.Request(url, headers={"User-Agent": EDGAR_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _keyword_check(text: str, keywords: list[str]) -> str | None:
    """Return first matched keyword or None."""
    lower = text.lower()
    for kw in keywords:
        if kw.lower() in lower:
            return kw
    return None


def _ticker_from_text(text: str) -> str | None:
    """Detect any tracked ticker mentioned in text."""
    upper = text.upper()
    for t in _tracked_tickers():
        if re.search(rf"\b{re.escape(t)}\b", upper):
            return t
    return None


def _record_alert(
    source_type: str,
    source_name: str,
    ticker: str | None,
    keyword: str,
    title: str,
    url: str,
    snippet: str,
    priority: str = "medium",
) -> int:
    """Persist a signal feed alert. Returns row id."""
    db.init()
    with db.connect() as cx:
        cur = cx.execute(
            "INSERT INTO signal_feed_alerts "
            "(source_type, source_name, ticker, keyword_matched, title, url, snippet, alert_priority) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source_type, source_name, ticker, keyword, title[:500], url, snippet[:1000], priority),
        )
        return cur.lastrowid or 0


# ─── EDGAR RSS full-text search ──────────────────────────────────────────────
EDGAR_FULLTEXT_RSS = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}&forms=10-K,10-Q,8-K&from=0&size=20"
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&forms=10-K,10-Q,8-K"


def scan_edgar_rss(keywords: list[str] | None = None) -> int:
    """Scan EDGAR full-text search for sole-source / key-supplier mentions.

    Uses the EDGAR EFTS (full-text search) API to find recent filings
    containing critical supply-chain keywords.

    Returns count of new alerts created.
    """
    kws = keywords or SOLE_SOURCE_KEYWORDS[:5]  # top 5 to avoid rate limiting
    created = 0

    for kw in kws:
        query = kw.replace(" ", "+")
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&forms=10-K,10-Q,8-K&dateRange=custom&startdt={(datetime.now(tz=UTC).strftime('%Y-%m-%d'))}&enddt={(datetime.now(tz=UTC).strftime('%Y-%m-%d'))}"
        body = _safe_get(url)
        if not body:
            continue

        # EFTS returns JSON; parse for filing entries
        try:
            import json
            data = json.loads(body)
            hits = data.get("hits", {}).get("hits", [])
        except Exception:
            hits = []

        for hit in hits[:10]:  # cap per keyword
            source = hit.get("_source", {})
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{source.get('file_num', '')}"
            title = source.get("display_names", [""])[0] if source.get("display_names") else ""
            entity = source.get("entity_name", "")
            ticker = _ticker_from_text(entity) or _ticker_from_text(title)
            snippet_text = f"{entity}: {title}"

            priority = "high" if ticker else "medium"
            _record_alert("edgar_rss", "EDGAR EFTS", ticker, kw, snippet_text, filing_url, snippet_text, priority)
            created += 1

    return created


# ─── Federal Register alerts ────────────────────────────────────────────────
FEDERAL_REGISTER_API = "https://www.federalregister.gov/api/v1/documents.json"


def scan_federal_register(keywords: list[str] | None = None) -> int:
    """Scan Federal Register for CHIPS Act / semiconductor keywords.

    Returns count of new alerts created.
    """
    import json

    kws = keywords or GOVT_KEYWORDS[:4]
    created = 0

    for kw in kws:
        url = f"{FEDERAL_REGISTER_API}?conditions[term]={kw.replace(' ', '+')}&per_page=5&order=newest"
        body = _safe_get(url)
        if not body:
            continue

        try:
            data = json.loads(body)
            results = data.get("results", [])
        except Exception:
            results = []

        for doc in results:
            title = doc.get("title", "")
            doc_url = doc.get("html_url", "")
            abstract = doc.get("abstract", "") or ""
            ticker = _ticker_from_text(title) or _ticker_from_text(abstract)
            snippet = f"{title[:200]}. {abstract[:300]}"
            priority = "high" if ticker else "low"
            _record_alert("federal_register", "Federal Register", ticker, kw, title, doc_url, snippet, priority)
            created += 1

    return created


# ─── Customer supplier page diff ────────────────────────────────────────────

def _compute_diff(old_content: str, new_content: str) -> tuple[list[str], list[str]]:
    """Compare two page contents and return (removed_names, added_names).

    Uses simple word-set diffing focused on proper-noun-like tokens.
    """
    name_re = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")
    old_names = set(name_re.findall(old_content))
    new_names = set(name_re.findall(new_content))
    removed = sorted(old_names - new_names)
    added = sorted(new_names - old_names)
    return removed, added


def scan_customer_pages() -> int:
    """Check registered customer supplier pages for changes.

    Returns count of new alerts created.
    """
    db.init()
    created = 0

    with db.connect() as cx:
        pages = cx.execute(
            "SELECT * FROM customer_supplier_pages WHERE enabled = 1"
        ).fetchall()

        for page in pages:
            body = _safe_get(page["page_url"])
            if not body:
                continue

            new_hash = hashlib.sha256(body.encode()).hexdigest()
            old_hash = page["last_content_sha256"]

            if old_hash and new_hash == old_hash:
                continue  # no change

            # Detect removed/added names
            removed: list[str] = []
            added: list[str] = []
            if old_hash:
                # We don't have old content cached, but we track removed names
                removed, added = [], []  # Full diff requires content cache

            cx.execute(
                "UPDATE customer_supplier_pages "
                "SET last_snapshot_at = datetime('now'), last_content_sha256 = ?, "
                "    removed_names = ?, added_names = ? "
                "WHERE id = ?",
                (new_hash, ",".join(removed), ",".join(added), page["id"]),
            )

            if old_hash:  # Only alert on changes, not first snapshot
                _record_alert(
                    "customer_page",
                    f"Page: {page['customer_ticker']}",
                    page["customer_ticker"],
                    "page_change",
                    f"Supplier page changed for {page['customer_ticker']}",
                    page["page_url"],
                    f"Hash changed: {old_hash[:12]}→{new_hash[:12]}",
                    "critical",
                )
                created += 1

    return created


# ─── Builtin customer supplier page registry ────────────────────────────────

BUILTIN_SUPPLIER_PAGES: list[dict[str, str]] = [
    {"customer_ticker": "NVDA", "page_url": "https://www.nvidia.com/en-us/about-nvidia/partners/", "page_label": "NVIDIA Partners"},
    {"customer_ticker": "MRVL", "page_url": "https://www.marvell.com/company/partners.html", "page_label": "Marvell Partners"},
    {"customer_ticker": "AVGO", "page_url": "https://www.broadcom.com/company/partner", "page_label": "Broadcom Partners"},
]


def import_builtin_pages() -> int:
    """Seed the customer supplier page registry. Returns rows inserted."""
    db.init()
    inserted = 0
    with db.connect() as cx:
        for p in BUILTIN_SUPPLIER_PAGES:
            try:
                cx.execute(
                    "INSERT OR IGNORE INTO customer_supplier_pages "
                    "(customer_ticker, page_url, page_label) VALUES (?, ?, ?)",
                    (p["customer_ticker"], p["page_url"], p["page_label"]),
                )
                if cx.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except Exception:
                continue
    return inserted


# ─── Unacknowledged alerts query ─────────────────────────────────────────────

def unacknowledged_alerts(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent unacknowledged signal feed alerts."""
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT * FROM signal_feed_alerts "
            "WHERE acknowledged = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def acknowledge_alert(alert_id: int) -> None:
    """Mark a signal feed alert as acknowledged."""
    with db.connect() as cx:
        cx.execute("UPDATE signal_feed_alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))


def scan_all() -> dict[str, int]:
    """Run all signal feed scans. Returns dict of source → count."""
    results: dict[str, int] = {}
    results["edgar_rss"] = scan_edgar_rss()
    results["federal_register"] = scan_federal_register()
    results["customer_pages"] = scan_customer_pages()
    return results
