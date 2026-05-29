"""Fetch the actual SEC filing document text (not just the Atom headline) and
run a Claude extraction prompt to pull structured evidence.

This is the bridge from 'we saw a headline' to 'we have an A/B/C grade'.
"""
from __future__ import annotations
import json
import re
import time
from urllib.parse import urljoin

import requests

from ..bridge_client import ask_json
from ..config import EDGAR_RPS, EDGAR_USER_AGENT
from .. import db

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _sleep() -> None:
    if EDGAR_RPS > 0:
        time.sleep(1.0 / EDGAR_RPS)


def fetch_text(url: str, max_chars: int = 60_000) -> str:
    """Fetch a filing URL and return cleaned plain text (truncated)."""
    _sleep()
    r = requests.get(url, headers=_headers(), timeout=45)
    r.raise_for_status()
    body = r.text
    # If it's an EDGAR filing index, follow first .htm document link
    if "<title>EDGAR" in body or "Filing Detail" in body[:2000]:
        m = re.search(r'href="(/Archives/edgar/data/[^"]+\.htm[ml]?)"', body, re.I)
        if m:
            doc_url = urljoin("https://www.sec.gov", m.group(1))
            _sleep()
            r = requests.get(doc_url, headers=_headers(), timeout=45)
            r.raise_for_status()
            body = r.text
    text = _HTML_TAG.sub(" ", body)
    text = _WHITESPACE.sub(" ", text).strip()
    return text[:max_chars]


EXTRACTION_SYSTEM = (
    "You extract structured supplier/customer/bottleneck evidence from SEC filing text. "
    "You return STRICT JSON only (no prose, no code fences). "
    "Be conservative: prefer 'unknown' over guessing."
)


EXTRACTION_USER_TMPL = """Given the SEC filing text below, extract evidence relevant to AI / semiconductor / photonics supply-chain bottlenecks.

Return JSON in this exact shape:
{{
  "tickers_mentioned": [],
  "supplier_relationships": [
    {{"supplier": "", "customer": "", "phrase": "", "grade": "A|B|C|D|U"}}
  ],
  "capacity_signals": [
    {{"signal": "", "company": "", "phrase": ""}}
  ],
  "chokepoint_themes": [],
  "summary": ""
}}

Evidence grading:
- A = customer's own filing explicitly says sole/primary/strategic supplier or names X by name as critical
- B = filing names a partnership without exclusivity wording
- C = filing only hints (evaluation, qualification, potential)
- D = no real evidence
- U = unclear

Filing text:
\"\"\"
{text}
\"\"\"
"""


def extract_evidence(text: str) -> dict:
    # Neutralise the triple-quote delimiter so a filing that itself contains
    # `\"\"\"` (or a prompt-injection payload using it) cannot break out of the
    # quoted block and rewrite our instructions (OWASP LLM01).
    safe_text = text[:55_000].replace('"""', '\u201c\u201c\u201c')
    user = EXTRACTION_USER_TMPL.format(text=safe_text)
    return ask_json(EXTRACTION_SYSTEM, user)


def enrich_filing(accession_no: str) -> dict | None:
    """Pull a stored filing, fetch its text, ask the LLM, persist evidence rows."""
    with db.connect() as cx:
        row = cx.execute(
            "SELECT accession_no, url, ticker FROM filings WHERE accession_no = ?",
            (accession_no,),
        ).fetchone()
        if not row:
            return None
        url = row["url"]
        text = fetch_text(url)
        result = extract_evidence(text)
        # Persist evidence rows
        for rel in (result.get("supplier_relationships") or []):
            db.insert_evidence(
                cx,
                {
                    "ticker": rel.get("supplier") or rel.get("customer") or row["ticker"] or "?",
                    "grade": (rel.get("grade") or "U")[:1],
                    "source_url": url,
                    "excerpt": (rel.get("phrase") or "")[:500],
                    "keywords": "supplier_relationship",
                },
            )
        return result


def enrich_recent(limit: int = 5) -> list[str]:
    """Enrich the most recently discovered filings that haven't been processed yet."""
    db.init()
    accs: list[str] = []
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT accession_no FROM filings ORDER BY discovered_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        accs = [r["accession_no"] for r in rows]
    out: list[str] = []
    for acc in accs:
        try:
            enrich_filing(acc)
            out.append(acc)
        except Exception as e:  # noqa: BLE001
            print(f"  enrich failed for {acc}: {e}")
    return out


def main() -> None:
    accs = enrich_recent()
    print(f"Enriched {len(accs)} filings.")


if __name__ == "__main__":
    main()
