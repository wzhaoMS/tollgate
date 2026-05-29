"""Tests for the sub-$10B screen candidate seeder + scoring integration."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_import_builtin_candidates(tmpdb):
    from src import db, scoring, seed_candidates

    n = seed_candidates.import_builtin_candidates()
    assert n == len(seed_candidates.BUILTIN_CANDIDATES)

    # New unverified names exist with grade 'U' and produce a defined decision.
    with db.connect() as cx:
        row = cx.execute("SELECT * FROM chokepoints WHERE ticker = 'LPK'").fetchone()
        assert row is not None
        assert row["evidence_grade"] == "U"
        score = scoring.score_row(cx, {k: row[k] for k in row.keys()})
        assert score["overall"] in {"Buy", "Watch", "Pass", "Skip"}
        # Unverified names cannot pass independent verification.
        assert score["independent_verification"] == "fail"


def test_candidate_market_caps_are_usd(tmpdb):
    from src import db, seed_candidates

    seed_candidates.import_builtin_candidates()

    with db.connect() as cx:
        rows = cx.execute(
            "SELECT ticker, market_cap_usd FROM chokepoints "
            "WHERE ticker IN ('LPK','VSH','POWL') ORDER BY market_cap_usd"
        ).fetchall()
    caps = {r["ticker"]: r["market_cap_usd"] for r in rows}
    # All normalized to USD and ordered small -> large as expected.
    assert caps["LPK"] < caps["VSH"] < caps["POWL"]
    assert caps["POWL"] > 10_000_000_000
