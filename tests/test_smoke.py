"""Smoke tests: schema creation, seed load, keyword filter, scorer + pair gen."""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_end_to_end():
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    os.environ["DB_PATH"] = str(tmp)
    for mod in [m for m in list(sys.modules) if m.startswith("src.")]:
        del sys.modules[mod]
    from src import db, seed, scoring, pair_trade, paper, drawdown
    from src.scrapers import edgar, customer_diff

    db.init()
    n_seed = seed.load_seed_csv()
    seed.write_keyword_dict()
    assert n_seed >= 9

    # Keyword scan
    hits = edgar._scan_keywords("We are the sole source of InP wafers.", {"a": ["sole source"]})
    assert any("sole source" in h for h in hits)

    # Scorer runs
    out = scoring.score_all()
    assert len(out) == n_seed
    for r in out:
        assert r["overall"] in {"Buy", "Watch", "Pass", "Skip"}

    # Customer diff cleaner produces text
    cleaned = customer_diff._clean("<html><script>x()</script>hello <b>world</b></html>")
    assert "hello" in cleaned and "x()" not in cleaned

    # Paper position round trip
    paper.open_position("TEST", 100, 10.0, notes="unit")
    assert any(p["ticker"] == "TEST" for p in paper.list_positions())

    # Re-opening an already-open ticker must NOT wipe its original cost basis
    first = next(p for p in paper.list_positions() if p["ticker"] == "TEST")
    paper.open_position("TEST", 999, 42.0, notes="should-not-apply")
    again = next(p for p in paper.list_positions() if p["ticker"] == "TEST")
    assert again["cost_basis"] == first["cost_basis"] == 10.0
    assert again["opened_at"] == first["opened_at"]
    paper.close_position("TEST")

    # Drawdown evaluator does not blow up on empty set
    drawdown.evaluate()

    # Pair candidates list is iterable (may be empty without prices)
    list(pair_trade.candidates())
