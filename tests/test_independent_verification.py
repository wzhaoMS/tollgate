"""Tests for the independent-verification gate (Tier F)."""
from __future__ import annotations

from src import scoring


def test_pass_when_recent_evidence_from_non_serenity_source(tmpdb):
    tmpdb.execute(
        "INSERT INTO evidence_log (ticker, grade, source_url) "
        "VALUES ('TST', 'A', 'https://www.sec.gov/edgar/x.htm')"
    )
    tmpdb.commit()
    assert scoring._independent_verification(tmpdb, "TST") == "pass"


def test_fail_when_only_evidence_is_from_twitter(tmpdb):
    tmpdb.execute(
        "INSERT INTO evidence_log (ticker, grade, source_url) "
        "VALUES ('TST', 'A', 'https://twitter.com/aleabitoreddit/123')"
    )
    tmpdb.execute(
        "INSERT INTO evidence_log (ticker, grade, source_url) "
        "VALUES ('TST', 'B', 'https://x.com/aleabitoreddit/124')"
    )
    tmpdb.commit()
    assert scoring._independent_verification(tmpdb, "TST") == "fail"


def test_fail_when_no_evidence(tmpdb):
    assert scoring._independent_verification(tmpdb, "TST") == "fail"


def test_pass_via_supplier_relationships(tmpdb):
    tmpdb.execute(
        "INSERT INTO supplier_relationships "
        "(supplier_ticker, evidence_grade, source_url, direction) "
        "VALUES ('TST', 'B', 'https://www.sec.gov/c.htm', 'customer_to_supplier')"
    )
    tmpdb.commit()
    assert scoring._independent_verification(tmpdb, "TST") == "pass"


def test_old_evidence_doesnt_count(tmpdb):
    tmpdb.execute(
        "INSERT INTO evidence_log (ticker, grade, source_url, extracted_at) "
        "VALUES ('TST', 'A', 'https://www.sec.gov/x.htm', datetime('now', '-120 days'))"
    )
    tmpdb.commit()
    assert scoring._independent_verification(tmpdb, "TST") == "fail"
