"""SEC EDGAR scraper. Pulls recent filings, filters by keyword dictionary, persists hits.

Uses the public Atom feed at /cgi-bin/browse-edgar (no auth, no API key). Respects
the SEC Fair Access policy: per-request User-Agent with contact, and self-throttled
to EDGAR_RPS req/sec.
"""
from __future__ import annotations
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import feedparser
import requests
from ..config import DATA_DIR, EDGAR_RPS, EDGAR_USER_AGENT
from .. import db

BROWSE_ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type={form}&company=&dateb=&owner=include&count={count}&output=atom"
)


@dataclass
class FilingHit:
    accession_no: str
    cik: str | None
    ticker: str | None
    form: str
    filed_at: str
    title: str
    url: str
    summary: str
    keyword_hits: list[str]


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _sleep() -> None:
    if EDGAR_RPS > 0:
        time.sleep(1.0 / EDGAR_RPS)


def _load_keywords() -> dict[str, list[str]]:
    p = DATA_DIR / "keywords.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def fetch_recent(form: str = "8-K", count: int = 100) -> list[dict]:
    """Pull the EDGAR 'getcurrent' Atom feed for a form type."""
    url = BROWSE_ATOM.format(form=form, count=count)
    _sleep()
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    out: list[dict] = []
    for e in parsed.entries:
        out.append(
            {
                "title": e.get("title", "") or "",
                "summary": e.get("summary", "") or "",
                "link": e.get("link", "") or "",
                "updated": e.get("updated", "") or e.get("published", "") or "",
                "id": e.get("id", "") or "",
            }
        )
    return out


_ACC_RE = re.compile(r"(\d{10}-\d{2}-\d{6})")
_CIK_RE = re.compile(r"CIK=(\d+)", re.IGNORECASE)


def _extract_accession(entry: dict) -> str:
    for field in ("link", "id", "title"):
        v = entry.get(field, "") or ""
        m = _ACC_RE.search(v)
        if m:
            return m.group(1)
    # fall back to a STABLE content hash so the same entry always maps to the
    # same primary key across runs (Python's built-in hash() is salted per
    # process via PYTHONHASHSEED and would create duplicate rows otherwise).
    seed = (entry.get("link") or entry.get("id") or entry.get("title") or "").encode("utf-8")
    digest = hashlib.sha1(seed).hexdigest()[:12]
    return f"NA-{digest}"


def _extract_cik(entry: dict) -> str | None:
    for field in ("link", "id", "title", "summary"):
        v = entry.get(field, "") or ""
        m = _CIK_RE.search(v)
        if m:
            return m.group(1)
    return None


def _scan_keywords(text: str, dictionary: dict[str, list[str]]) -> list[str]:
    hay = text.lower()
    hits: list[str] = []
    for bucket, kws in dictionary.items():
        for kw in kws:
            if kw.lower() in hay:
                hits.append(f"{bucket}:{kw}")
    return hits


def harvest(forms: Iterable[str] = ("8-K", "10-Q", "10-K"), per_form: int = 100) -> int:
    """Pull recent filings for each form, keyword-filter, store hits. Returns # new rows."""
    kw = _load_keywords()
    if not kw:
        raise SystemExit(
            "No keywords.json found. Run `py -m src.seed` first to generate it."
        )
    db.init()
    inserted = 0
    with db.connect() as cx:
        for form in forms:
            entries = fetch_recent(form=form, count=per_form)
            for e in entries:
                blob = f"{e.get('title','')}\n{e.get('summary','')}"
                hits = _scan_keywords(blob, kw)
                if not hits:
                    continue
                row = {
                    "accession_no": _extract_accession(e),
                    "cik": _extract_cik(e),
                    "ticker": None,
                    "form": form,
                    "filed_at": e.get("updated") or "",
                    "title": e.get("title") or "",
                    "url": e.get("link") or "",
                    "summary": e.get("summary") or "",
                    "keyword_hits": ",".join(hits),
                    "raw_json": json.dumps(e),
                }
                if db.insert_filing(cx, row):
                    inserted += 1
    return inserted


def main() -> None:
    n = harvest()
    print(f"Inserted {n} new keyword-filtered filings.")


if __name__ == "__main__":
    main()
