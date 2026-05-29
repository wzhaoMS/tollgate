"""Offline unit tests for parsing/extraction helpers and the bridge retry
predicate. No network access required."""
from __future__ import annotations

import requests

from src.bridge_client import _is_retryable
from src.enrich import filing_full
from src.scrapers import edgar, insider_form4

# ---- EDGAR keyword scan + entry helpers ----------------------------------

def test_scan_keywords_matches_bucket():
    hits = edgar._scan_keywords(
        "The Company is the sole source of InP wafers.",
        {"supplier_lock": ["sole source"], "noise": ["unrelated"]},
    )
    assert hits == ["supplier_lock:sole source"]


def test_scan_keywords_is_case_insensitive():
    hits = edgar._scan_keywords("CHIPS ACT award", {"govt": ["chips act"]})
    assert hits == ["govt:chips act"]


def test_entry_form_type_prefers_category_term():
    e = {"tags": [{"term": "8-K"}], "title": "8-K - FOO (123) (Filer)"}
    assert edgar._entry_form_type(e) == "8-K"


def test_entry_form_type_falls_back_to_title():
    e = {"tags": [], "title": "10-Q - FOO (123) (Filer)"}
    assert edgar._entry_form_type(e) == "10-Q"


def test_extract_accession_from_link():
    e = {"link": "https://sec.gov/Archives/.../0001234567-26-000123-index.htm"}
    assert edgar._extract_accession(e) == "0001234567-26-000123"


def test_extract_accession_is_deterministic_fallback():
    e = {"link": "https://example.com/no-accession-here", "id": "", "title": ""}
    a = edgar._extract_accession(e)
    b = edgar._extract_accession(e)
    assert a == b and a.startswith("NA-")


# ---- Form 4 XML parsing ---------------------------------------------------

_FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer><issuerTradingSymbol>TST</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>0</isOfficer></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-05-01</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_parse_form4_extracts_transaction():
    txns = insider_form4._parse_form4_xml(_FORM4)
    assert len(txns) == 1
    t = txns[0]
    assert t["ticker"] == "TST"
    assert t["filer_name"] == "DOE JANE"
    assert "director" in (t["relation"] or "")
    assert t["txn_code"] == "P"
    assert t["shares"] == 1000.0
    assert t["price"] == 12.5
    assert t["dollar_amount"] == 12500.0


def test_form4_type_filter_constant():
    assert "4" in insider_form4._FORM4_TYPES
    assert "4/A" in insider_form4._FORM4_TYPES


# ---- filing primary-document URL resolution ------------------------------

def test_normalize_doc_href_unwraps_ixbrl_viewer():
    # EDGAR links the primary doc through the inline-XBRL viewer; fetching that
    # returns a JS shell with no text, so it must be unwrapped to the raw path.
    href = "/ix?doc=/Archives/edgar/data/123/000.../doc.htm"
    assert filing_full._normalize_doc_href(href) == "/Archives/edgar/data/123/000.../doc.htm"


def test_normalize_doc_href_passes_through_raw_archive_path():
    href = "/Archives/edgar/data/123/000.../doc.htm"
    assert filing_full._normalize_doc_href(href) == href


def test_normalize_doc_href_rejects_non_archive_links():
    assert filing_full._normalize_doc_href("/cgi-bin/browse-edgar") is None
    assert filing_full._normalize_doc_href("") is None


def test_rfile_pattern_skips_xbrl_rfiles():
    assert filing_full._RFILE.search("/archives/edgar/data/1/r1.htm")
    assert not filing_full._RFILE.search("/archives/edgar/data/1/aaoi_10k.htm")


# ---- bridge retry predicate ----------------------------------------------

def _http_error(status):
    resp = requests.Response()
    resp.status_code = status
    return requests.HTTPError(response=resp)


def test_retryable_on_timeout_and_connection():
    assert _is_retryable(requests.Timeout()) is True
    assert _is_retryable(requests.ConnectionError()) is True


def test_retryable_on_5xx_not_4xx():
    assert _is_retryable(_http_error(503)) is True
    assert _is_retryable(_http_error(500)) is True
    assert _is_retryable(_http_error(404)) is False
    assert _is_retryable(_http_error(400)) is False


def test_not_retryable_on_generic_error():
    assert _is_retryable(ValueError("nope")) is False
