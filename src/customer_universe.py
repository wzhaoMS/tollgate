"""Derive the *customer* universe from ``chokepoints.end_customer`` so we can
harvest the customers' own SEC filings.

The point of step 1 in Serenity's checklist is to find supplier evidence in
*customer* filings (the customer is the one legally obligated to disclose a
sole-source dependency). Today, our harvest only pulls each chokepoint's
*own* filings, which means ``customer_relationships`` extraction has nothing
to scan.

This module:

- parses upper-case ticker-shaped tokens out of the free-text
  ``end_customer`` column (skipping known non-ticker words and
  already-tracked chokepoint tickers),
- returns a deduplicated, sorted list of candidate customer tickers.
"""
from __future__ import annotations

import re

from . import db

# Skip common English / acronym noise so we don't try to "harvest" AI or DC.
_STOPWORDS = {
    "AI", "DC", "TPU", "RAN", "DCI", "CPO", "HBM", "SOI", "SIC", "INP", "GAN",
    "EV", "PV", "EU", "US", "USA", "OEM", "ODM", "OS", "IT", "OT", "DRAM",
    "NAND", "ASIC", "FAB", "DOE", "NIST", "SEC", "AND", "OR", "THE", "FOR",
    "WITH", "FROM", "VIA", "TO", "OF", "IN", "ON", "AT", "BY", "RS",
}

# Token must be word-bounded uppercase 2-5 chars; we split on non-letter
# separators first so "FOXCONN" doesn't accidentally yield "FOXCO".
_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9.\-]{1,4}\b")

# Conservative allowlist of customer tickers we actually expect to find in
# ``chokepoints.end_customer`` text. Restricting to known tickers prevents us
# from hammering EDGAR with garbage tokens parsed out of free-text labels
# (e.g. "Hyperscalers", "Foxconn", "Sovereign AI") that aren't tickers.
_KNOWN_PUBLIC_CUSTOMERS = {
    "NVDA", "AMD", "INTC", "MU", "AMZN", "MSFT", "GOOG", "GOOGL", "META",
    "AAPL", "TSLA", "TSM", "AVGO", "MRVL", "QCOM", "ORCL", "IBM", "DELL",
    "HPE", "SMCI", "ANET", "CSCO", "NOK", "ERIC", "CIEN", "JNPR", "LITE",
    "COHR", "AAOI", "GFS", "WDC", "STX",
}


def _is_ticker_like(token: str) -> bool:
    if token in _STOPWORDS:
        return False
    if len(token) < 2 or len(token) > 5:
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]*", token))


def extract_customer_tickers() -> list[str]:
    """Return distinct customer-ticker candidates from chokepoints.end_customer.

    Tickers that already appear in ``chokepoints.ticker`` are excluded so we
    don't re-harvest our own universe via this entry point.
    """
    db.init()
    own = set()
    raw: list[str] = []
    with db.connect() as cx:
        for r in cx.execute("SELECT ticker, end_customer FROM chokepoints"):
            if r["ticker"]:
                own.add(r["ticker"].upper())
            ec = r["end_customer"] or ""
            if ec:
                raw.append(ec)
    candidates: set[str] = set()
    for text in raw:
        for tok in _TOKEN_RE.findall(text.upper()):
            if not _is_ticker_like(tok):
                continue
            if tok in own:
                continue
            if tok not in _KNOWN_PUBLIC_CUSTOMERS:
                continue
            candidates.add(tok)
    return sorted(candidates)


def main() -> None:
    tickers = extract_customer_tickers()
    print(f"customer universe ({len(tickers)}):", ", ".join(tickers))


if __name__ == "__main__":
    main()
