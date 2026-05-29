"""SEC Form 4 insider-transaction harvest.

Pulls the EDGAR atom feed for Form 4 filings, extracts key fields from each
filing's XML body. Form 4 has a clean machine-readable XML doc per filing.
"""
from __future__ import annotations
import re
import time
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from ..config import EDGAR_RPS, EDGAR_USER_AGENT
from .. import db

ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=4&company=&dateb=&owner=include&count={count}&output=atom"
)


def _headers() -> dict[str, str]:
    return {"User-Agent": EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _sleep() -> None:
    if EDGAR_RPS > 0:
        time.sleep(1.0 / EDGAR_RPS)


def _atom_entries(count: int) -> list[dict]:
    _sleep()
    r = requests.get(ATOM.format(count=count), headers=_headers(), timeout=30)
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    out: list[dict] = []
    for e in parsed.entries:
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
    """Filing index page lists the XML primary doc; return its URL."""
    _sleep()
    r = requests.get(filing_index_url, headers=_headers(), timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.select("a"):
        href = a.get("href") or ""
        if href.lower().endswith(".xml") and "form" in href.lower():
            return urljoin(filing_index_url, href)
    # fallback: first xml link
    for a in soup.select("a"):
        href = a.get("href") or ""
        if href.lower().endswith(".xml"):
            return urljoin(filing_index_url, href)
    return None


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


def harvest(count: int = 100) -> int:
    db.init()
    inserted = 0
    entries = _atom_entries(count)
    with db.connect() as cx:
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
                    cx.execute(
                        f"INSERT OR IGNORE INTO insider_txns ({','.join(cols)}) "
                        f"VALUES ({','.join('?' for _ in cols)})",
                        [row[c] for c in cols],
                    )
                    inserted += 1
            except Exception as ex:  # noqa: BLE001
                print(f"  [form4 err] {acc}: {ex}")
    return inserted


def main() -> None:
    n = harvest()
    print(f"Inserted {n} insider transactions.")


if __name__ == "__main__":
    main()
