"""Mocked network-adapter tests for external feed clients."""
from __future__ import annotations

from src.enrich import filing_full
from src.scrapers import edgar, insider_form4


class _Resp:
    def __init__(self, text: str, *, ok: bool = True, status_code: int = 200):
        self.text = text
        self.content = text.encode("utf-8")
        self.ok = ok
        self.status_code = status_code

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


def _atom(entries: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  {entries}
</feed>
"""


def _entry(title: str, category: str, link: str) -> str:
    return f"""
  <entry>
    <title>{title}</title>
    <category term="{category}" />
    <link href="{link}" />
    <updated>2026-05-29T00:00:00-04:00</updated>
    <summary>summary</summary>
    <id>{link}</id>
  </entry>
"""


def test_edgar_fetch_company_filters_exact_form_types(monkeypatch):
    xml = _atom(
        _entry("10-K - TST", "10-K", "https://sec.gov/Archives/a/0000000000-26-000001-index.htm")
        + _entry("10-K/A - TST", "10-K/A", "https://sec.gov/Archives/a/0000000000-26-000002-index.htm")
        + _entry("10-Q - TST", "10-Q", "https://sec.gov/Archives/a/0000000000-26-000003-index.htm")
    )
    monkeypatch.setattr(edgar.requests, "get", lambda *args, **kwargs: _Resp(xml))

    rows = edgar.fetch_company("TST", "10-K", count=40)
    assert [r["title"] for r in rows] == ["10-K - TST", "10-K/A - TST"]


def test_filing_full_resolver_unwraps_ixbrl_viewer(monkeypatch):
    html = """
    <html><body>
      <table class="tableFile">
        <tr><td><a href="/ix?doc=/Archives/edgar/data/123/000/doc10k.htm">doc</a></td></tr>
      </table>
    </body></html>
    """
    monkeypatch.setattr(filing_full.requests, "get", lambda *args, **kwargs: _Resp(html))

    assert filing_full._resolve_primary_doc("https://www.sec.gov/Archives/edgar/data/123/index.htm") == (
        "https://www.sec.gov/Archives/edgar/data/123/000/doc10k.htm"
    )


def test_form4_atom_entries_filters_prefix_noise(monkeypatch):
    xml = _atom(
        _entry("4 - Insider", "4", "https://sec.gov/Archives/a/0000000000-26-000004-index.htm")
        + _entry("4/A - Insider", "4/A", "https://sec.gov/Archives/a/0000000000-26-000005-index.htm")
        + _entry("40-F - Issuer", "40-F", "https://sec.gov/Archives/a/0000000000-26-000006-index.htm")
    )
    monkeypatch.setattr(insider_form4.requests, "get", lambda *args, **kwargs: _Resp(xml))

    rows = insider_form4._atom_entries("TST", count=40)
    assert [r["title"] for r in rows] == ["4 - Insider", "4/A - Insider"]
