"""Smoke tests: schema creation, seed load, keyword filter, scorer runs end-to-end."""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

# Ensure we can import the project even when pytest auto-discovers
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_end_to_end():
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    os.environ["DB_PATH"] = str(tmp)
    # Force re-import with new DB_PATH
    for mod in [m for m in list(sys.modules) if m.startswith("src.")]:
        del sys.modules[mod]
    from src import db, seed, scoring
    from src.scrapers import edgar

    db.init()
    n_seed = seed.load_seed_csv()
    seed.write_keyword_dict()
    assert n_seed >= 9, f"expected at least 9 seeded rows, got {n_seed}"

    # Keyword scan on synthetic text
    kw = {"supplier_lock": ["sole source"], "themes": ["indium phosphide"]}
    hits = edgar._scan_keywords("We are the sole source of InP-related wafers.", kw)
    assert any("sole source" in h for h in hits)

    # Scorer runs and writes
    out = scoring.score_all()
    assert len(out) == n_seed
    for r in out:
        assert r["overall"] in {"Buy", "Watch", "Pass", "Skip"}
