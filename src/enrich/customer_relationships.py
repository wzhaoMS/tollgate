"""Customer-filing reverse verification (Step 1 of the original plan).

Scan filing bodies for evidence that a *customer's* document names a chokepoint
*supplier* and describes the relationship as critical / sole / single-source /
primary. Persist matches into ``supplier_relationships`` so step_1 of the
scoring checklist has graded, auditable evidence instead of relying purely on
curated rows.

This is intentionally conservative:

- Only scans filings whose ``summary`` body has been fetched (>= 500 chars).
- Requires BOTH (a) the supplier ticker token to appear and
  (b) a dependency phrase from ``_DEPENDENCY_PHRASES`` within a short window.
- Skips filings whose ``ticker`` matches the supplier (those are not the
  customer's filing).
- Idempotent: a UNIQUE-ish check on (supplier_ticker, customer_ticker,
  source_accession_no) prevents duplicate rows on re-runs.
"""
from __future__ import annotations

import re

from .. import db

_DEPENDENCY_PHRASES = (
    "sole supplier",
    "single source",
    "single-source",
    "sole source",
    "sole-source",
    "primary supplier",
    "critical supplier",
    "key supplier",
    "depend on",
    "depends on",
    "rely on",
    "reliance on",
    "no alternative supplier",
    "limited number of suppliers",
)

# Within this many chars of the supplier mention, a dependency phrase counts.
_WINDOW = 400


def _supplier_pattern(ticker: str) -> re.Pattern[str]:
    # Match the ticker as a standalone token (avoid prefix collisions like
    # "AMD" matching "AMDOCS"). Allow optional $ prefix.
    return re.compile(rf"(?<![A-Z0-9])\$?{re.escape(ticker.upper())}(?![A-Z0-9])")


def _phrase_near(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - _WINDOW): end + _WINDOW].lower()
    for phrase in _DEPENDENCY_PHRASES:
        if phrase in window:
            return phrase
    return None


def _excerpt(text: str, start: int, end: int, pad: int = 160) -> str:
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    snippet = text[a:b].strip()
    return re.sub(r"\s+", " ", snippet)[:600]


def _already_recorded(
    cx,
    supplier: str,
    customer_ticker: str | None,
    accession: str | None,
) -> bool:
    row = cx.execute(
        "SELECT 1 FROM supplier_relationships "
        "WHERE supplier_ticker = ? "
        "AND IFNULL(customer_ticker,'') = IFNULL(?, '') "
        "AND IFNULL(source_accession_no,'') = IFNULL(?, '') LIMIT 1",
        (supplier.upper(), (customer_ticker or "").upper() or None, accession),
    ).fetchone()
    return row is not None


def extract_from_filings(*, limit: int = 500) -> dict:
    """Scan recent filings with bodies and persist matched relationships.

    Returns counts: scanned, matched, inserted, skipped_existing.
    """
    db.init()
    results = {"scanned": 0, "matched": 0, "inserted": 0, "skipped_existing": 0}
    with db.connect() as cx:
        suppliers = [
            r["ticker"].upper()
            for r in cx.execute("SELECT ticker FROM chokepoints WHERE ticker IS NOT NULL")
            if r["ticker"]
        ]
        patterns = {s: _supplier_pattern(s) for s in suppliers}
        rows = cx.execute(
            "SELECT accession_no, ticker, url, summary FROM filings "
            "WHERE summary IS NOT NULL AND length(summary) >= 500 "
            "ORDER BY filed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        for row in rows:
            results["scanned"] += 1
            text = row["summary"] or ""
            filer = (row["ticker"] or "").upper()
            for supplier, pat in patterns.items():
                if supplier == filer:
                    continue  # supplier's own filing isn't customer evidence
                m = pat.search(text)
                if not m:
                    continue
                phrase = _phrase_near(text, m.start(), m.end())
                if not phrase:
                    continue
                results["matched"] += 1
                if _already_recorded(cx, supplier, filer or None, row["accession_no"]):
                    results["skipped_existing"] += 1
                    continue
                cx.execute(
                    "INSERT INTO supplier_relationships "
                    "(supplier_ticker, customer_name, customer_ticker, "
                    " source_accession_no, source_url, source_type, "
                    " evidence_grade, relationship_type, phrase, direction, confidence) "
                    "VALUES (?, ?, ?, ?, ?, 'filing', 'B', ?, ?, 'customer_to_supplier', ?)",
                    (
                        supplier,
                        filer or None,
                        filer or None,
                        row["accession_no"],
                        row["url"],
                        phrase.replace(" ", "_"),
                        _excerpt(text, m.start(), m.end()),
                        0.7,
                    ),
                )
                results["inserted"] += 1
    return results


def main() -> None:
    res = extract_from_filings()
    print(
        f"customer-filing extraction: scanned={res['scanned']}, "
        f"matched={res['matched']}, inserted={res['inserted']}, "
        f"skipped_existing={res['skipped_existing']}"
    )


if __name__ == "__main__":
    main()
