"""Tests for the obvious-trade -> supplier graph."""
from __future__ import annotations

from src import supply_chain


def test_import_builtin_creates_links(tmpdb):
    n = supply_chain.import_builtin()
    assert n == len(supply_chain.BUILTIN_LINKS)
    nvda = supply_chain.upstream_for("NVDA")
    tickers = [r["supplier_ticker"] for r in nvda]
    assert "XFAB" in tickers
    # Ranked by link strength descending
    strengths = [r["link_strength"] for r in nvda]
    assert strengths == sorted(strengths, reverse=True)


def test_record_link_is_idempotent(tmpdb):
    supply_chain.record_link(
        obvious_ticker="nvda", supplier_ticker="xfab", link_strength=0.9, rationale="r1"
    )
    supply_chain.record_link(
        obvious_ticker="NVDA", supplier_ticker="XFAB", link_strength=0.95, rationale="r2"
    )
    rows = supply_chain.upstream_for("NVDA")
    assert len(rows) == 1
    assert rows[0]["link_strength"] == 0.95
    assert rows[0]["rationale"] == "r2"


def test_downstream_for_reverses_lookup(tmpdb):
    supply_chain.import_builtin()
    # SIVE is upstream for MRVL and AVGO in the seed.
    out = supply_chain.downstream_for("SIVE")
    obvious = {r["obvious_ticker"] for r in out}
    assert "MRVL" in obvious
    assert "AVGO" in obvious


def test_upstream_includes_score_when_available(tmpdb):
    supply_chain.import_builtin()
    tmpdb.execute(
        "INSERT INTO chokepoints (ticker, market_cap_usd) VALUES ('XFAB', 1_200_000_000)"
    )
    tmpdb.execute(
        "INSERT INTO scores (ticker, overall) VALUES ('XFAB', 'Watch')"
    )
    tmpdb.commit()
    out = supply_chain.upstream_for("NVDA")
    xfab = [r for r in out if r["supplier_ticker"] == "XFAB"][0]
    assert xfab["overall"] == "Watch"
    assert xfab["market_cap_usd"] == 1_200_000_000
