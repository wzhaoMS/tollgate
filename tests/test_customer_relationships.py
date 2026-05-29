"""Tests for customer-filing reverse-verification extraction."""
from __future__ import annotations

from src.enrich import customer_relationships


def _seed_chokepoint(cx, ticker: str) -> None:
    cx.execute(
        "INSERT OR IGNORE INTO chokepoints (ticker, chokepoint) VALUES (?, ?)",
        (ticker.upper(), f"{ticker} chokepoint"),
    )
    cx.commit()


def _seed_filing(cx, accession: str, ticker: str, body: str) -> None:
    cx.execute(
        "INSERT INTO filings (accession_no, ticker, form, filed_at, title, url, summary) "
        "VALUES (?, ?, '10-K', '2026-01-01', 't', 'http://x', ?)",
        (accession, ticker.upper(), body),
    )
    cx.commit()


def test_extract_records_customer_dependency(tmpdb):
    _seed_chokepoint(tmpdb, "XFAB")
    body = "We " + ("x " * 200) + " currently rely on XFAB as a sole supplier of GaN wafers. " + ("y " * 200)
    _seed_filing(tmpdb, "0000-26-000001", "AAPL", body)

    res = customer_relationships.extract_from_filings(limit=10)
    assert res["scanned"] == 1
    assert res["matched"] == 1
    assert res["inserted"] == 1

    row = tmpdb.execute(
        "SELECT supplier_ticker, customer_ticker, direction, evidence_grade, "
        "relationship_type, phrase FROM supplier_relationships"
    ).fetchone()
    assert row["supplier_ticker"] == "XFAB"
    assert row["customer_ticker"] == "AAPL"
    assert row["direction"] == "customer_to_supplier"
    assert row["evidence_grade"] == "B"
    assert row["relationship_type"] in {"sole_supplier", "rely_on"}
    assert "XFAB" in row["phrase"]


def test_extract_is_idempotent(tmpdb):
    _seed_chokepoint(tmpdb, "XFAB")
    body = "We rely on XFAB as a sole supplier of GaN wafers."
    _seed_filing(tmpdb, "0000-26-000002", "AAPL", body + " " * 500)

    customer_relationships.extract_from_filings(limit=10)
    res2 = customer_relationships.extract_from_filings(limit=10)
    assert res2["matched"] == 1
    assert res2["inserted"] == 0
    assert res2["skipped_existing"] == 1


def test_extract_skips_suppliers_own_filing(tmpdb):
    _seed_chokepoint(tmpdb, "XFAB")
    body = "XFAB is the sole supplier in this market." + (" " * 500)
    _seed_filing(tmpdb, "0000-26-000003", "XFAB", body)

    res = customer_relationships.extract_from_filings(limit=10)
    assert res["matched"] == 0


def test_extract_requires_dependency_phrase_near_ticker(tmpdb):
    _seed_chokepoint(tmpdb, "XFAB")
    body = "XFAB had a good quarter." + (" " * 600)  # no dependency language
    _seed_filing(tmpdb, "0000-26-000004", "AAPL", body)

    res = customer_relationships.extract_from_filings(limit=10)
    assert res["matched"] == 0


def test_extract_avoids_prefix_collisions(tmpdb):
    _seed_chokepoint(tmpdb, "AMD")
    body = "AMDOCS is our sole supplier of billing software." + (" " * 500)
    _seed_filing(tmpdb, "0000-26-000005", "VZ", body)

    res = customer_relationships.extract_from_filings(limit=10)
    assert res["matched"] == 0
