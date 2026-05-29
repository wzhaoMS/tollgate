"""Test customer-ticker extraction from chokepoints.end_customer."""
from __future__ import annotations

from src import customer_universe


def _seed(cx, ticker: str, end_customer: str | None) -> None:
    cx.execute(
        "INSERT OR REPLACE INTO chokepoints (ticker, end_customer) VALUES (?, ?)",
        (ticker, end_customer),
    )
    cx.commit()


def test_extracts_uppercase_tickers_and_skips_known_words(tmpdb):
    _seed(tmpdb, "XFAB", "NVDA/NOK (in evaluation)")
    _seed(tmpdb, "AAOI", "MSFT Maia/AMZN Trainium")
    _seed(tmpdb, "LITE", "Google TPU / NVDA")
    _seed(tmpdb, "CRDO", "AMZN/MSFT/GOOG")

    out = customer_universe.extract_customer_tickers()
    # Tracked chokepoint tickers themselves are excluded; AI/TPU stopwords too.
    assert "NVDA" in out
    assert "NOK" in out
    assert "MSFT" in out
    assert "AMZN" in out
    assert "GOOG" in out
    assert "TPU" not in out
    assert "AI" not in out
    assert "XFAB" not in out  # own ticker
    assert "AAOI" not in out


def test_returns_empty_when_no_end_customers(tmpdb):
    _seed(tmpdb, "SIVE", None)
    _seed(tmpdb, "IQE", "")
    assert customer_universe.extract_customer_tickers() == []


def test_handles_punctuation_and_lowercase(tmpdb):
    _seed(tmpdb, "WOLF", "nvda, auto, grid; Tesla")
    out = customer_universe.extract_customer_tickers()
    # uppercased internally → NVDA passes; "Tesla" is not all-caps so it's
    # ignored. The point is: NVDA still gets picked up.
    assert "NVDA" in out


def test_filters_out_unknown_words_even_when_token_shaped(tmpdb):
    _seed(tmpdb, "SIVE", "Foxconn, Hyperscalers, FOO, BARZ")
    out = customer_universe.extract_customer_tickers()
    # None of these are in the public-customer allowlist.
    assert out == []
