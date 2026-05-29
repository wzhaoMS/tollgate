"""SEC Form 4 insider-transaction harvest.

Queries EDGAR per tracked ticker (browse-edgar getcompany) and extracts key
fields from each Form 4 filing's XML body. Form 4 has a clean machine-readable
XML doc per filing.

Note: EDGAR's ``type`` filter is a prefix match (``type=4`` also returns 40-F,
497, 497K, etc.), so we filter each entry down to the exact form type before
fetching it.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from .. import db
from ..config import EDGAR_RPS, EDGAR_USER_AGENT

# Per-company query: ``CIK`` accepts a ticker symbol and EDGAR resolves it.
COMPANY_ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&CIK={ticker}&type=4&dateb=&owner=include"
    "&count={count}&output=atom"
)

# Exact Form 4 variants we accept (everything else from the prefix match is dropped).
_FORM4_TYPES = {"4", "4/A"}


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _sleep() -> None:
    if EDGAR_RPS > 0:
        time.sleep(1.0 / EDGAR_RPS)


def _entry_form_type(e) -> str | None:
    """Best-effort extraction of the exact form type from an atom entry."""
    for tag in e.get("tags", []) or []:
        term = (tag.get("term") or "").strip()
        if term:
            return term
    # Fallback: titles look like "4 - DOE JOHN (0001234567) (Reporting)".
    title = e.get("title", "") or ""
    head = title.split(" - ", 1)[0].strip()
    return head or None


def _atom_entries(ticker: str, count: int) -> list[dict]:
    _sleep()
    r = requests.get(
        COMPANY_ATOM.format(ticker=ticker, count=count),
        headers=_headers(),
        timeout=30,
    )
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    out: list[dict] = []
    for e in parsed.entries:
        form_type = _entry_form_type(e)
        if form_type not in _FORM4_TYPES:
            continue
        out.append(
            {
                "title": e.get("title", "") or "",
                "summary": e.get("summary", "") or "",
                "link": e.get("link", "") or "",
                "updated": e.get("updated", "") or "",
            }
        )
    return out


_ACC_RE = re.compile(r"(\d{10}-\d{2}-\d{6})")


def _accession(entry: dict) -> str | None:
    m = _ACC_RE.search(entry.get("link") or "")
    return m.group(1) if m else None


def _fetch_index(filing_index_url: str) -> str | None:
    """Filing index page lists the XML primary doc; return its URL.

    The index also links an ``xslF345X0?/`` styled-viewer transform of the same
    document, which is meant for browsers (and intermittently 503s). We skip any
    ``xsl``-prefixed path and return the raw machine-readable primary XML.
    """
    _sleep()
    r = requests.get(filing_index_url, headers=_headers(), timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    candidates: list[str] = []
    for a in soup.select("a"):
        href = a.get("href") or ""
        if not href.lower().endswith(".xml"):
            continue
        if "xsl" in href.lower():
            continue  # styled viewer transform, not the raw doc
        candidates.append(urljoin(filing_index_url, href))
    # Prefer a primary-document name (e.g. wf-form4_*.xml / form4.xml).
    for url in candidates:
        if "form" in url.lower():
            return url
    return candidates[0] if candidates else None


def _parse_form4_xml(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    issuer = soup.find("issuerTradingSymbol")
    ticker = issuer.text.strip().upper() if issuer and issuer.text else None
    owner = soup.find("rptOwnerName")
    filer_name = owner.text.strip() if owner and owner.text else None
    is_director = soup.find("isDirector")
    is_officer = soup.find("isOfficer")
    relation_bits = []
    if is_director and is_director.text and is_director.text.strip() in {"1", "true"}:
        relation_bits.append("director")
    if is_officer and is_officer.text and is_officer.text.strip() in {"1", "true"}:
        relation_bits.append("officer")
    relation = ",".join(relation_bits) or None

    txns: list[dict] = []
    for t in soup.find_all(["nonDerivativeTransaction", "derivativeTransaction"]):
        try:
            date_el = t.find("transactionDate")
            code_el = t.find("transactionCode")
            shares_el = t.find("transactionShares")
            price_el = t.find("transactionPricePerShare")
            shares_v = float(shares_el.find("value").text) if shares_el and shares_el.find("value") else None
            price_v = float(price_el.find("value").text) if price_el and price_el.find("value") and price_el.find("value").text else None
            txns.append(
                {
                    "ticker": ticker,
                    "filer_name": filer_name,
                    "relation": relation,
                    "txn_date": date_el.find("value").text if date_el and date_el.find("value") else None,
                    "txn_code": code_el.text.strip() if code_el and code_el.text else None,
                    "shares": shares_v,
                    "price": price_v,
                    "dollar_amount": (shares_v * price_v) if (shares_v and price_v) else None,
                }
            )
        except Exception:  # noqa: BLE001
            continue
    return txns


def _tracked_tickers(cx) -> list[str]:
    return [r[0] for r in cx.execute("SELECT ticker FROM chokepoints ORDER BY ticker")]


def _harvest_ticker(cx, ticker: str, count: int) -> int:
    inserted = 0
    try:
        entries = _atom_entries(ticker, count)
    except Exception as ex:  # noqa: BLE001
        print(f"  [form4 feed err] {ticker}: {ex}")
        return 0
    for e in entries:
        acc = _accession(e)
        if not acc:
            continue
        try:
            xml_url = _fetch_index(e["link"])
            if not xml_url:
                continue
            _sleep()
            r = requests.get(xml_url, headers=_headers(), timeout=30)
            r.raise_for_status()
            for txn in _parse_form4_xml(r.text):
                if not txn["ticker"]:
                    continue
                row = {"accession_no": acc, "url": xml_url, **txn}
                cols = list(row.keys())
                cur = cx.execute(
                    f"INSERT OR IGNORE INTO insider_txns ({','.join(cols)}) "
                    f"VALUES ({','.join('?' for _ in cols)})",
                    [row[c] for c in cols],
                )
                inserted += cur.rowcount or 0
        except Exception as ex:  # noqa: BLE001
            print(f"  [form4 err] {ticker} {acc}: {ex}")
    return inserted


def harvest(count: int = 40, tickers: list[str] | None = None) -> int:
    db.init()
    inserted = 0
    with db.connect() as cx:
        targets = tickers or _tracked_tickers(cx)
        for ticker in targets:
            n = _harvest_ticker(cx, ticker, count)
            if n:
                print(f"  [{ticker}] +{n} insider txns")
            inserted += n
    return inserted


def main() -> None:
    n = harvest()
    print(f"Inserted {n} insider transactions.")


if __name__ == "__main__":
    main()
