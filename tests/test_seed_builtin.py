"""Tests for the seed_builtin module — seeding all empty tables."""
from __future__ import annotations

from src import seed_builtin


def test_seed_all_populates_tables(tmpdb):
    results = seed_builtin.seed_all()
    assert results["capacity_models"] > 0
    assert results["substitution_assessments"] > 0
    assert results["catalyst_events"] > 0
    assert results["consensus_metrics"] > 0
    assert results["serenity_signals"] > 0
    assert results["follower_history"] > 0


def test_seed_all_is_idempotent(tmpdb):
    seed_builtin.seed_all()
    r2 = seed_builtin.seed_all()
    # Second run should insert zero or near-zero (consensus uses REPLACE)
    assert r2["capacity_models"] == 0
    assert r2["serenity_signals"] == 0
    assert r2["follower_history"] == 0


def test_capacity_models_populated(tmpdb):
    seed_builtin.seed_all()
    rows = tmpdb.execute("SELECT COUNT(*) FROM capacity_models").fetchone()[0]
    assert rows == len(seed_builtin.BUILTIN_CAPACITY_MODELS)


def test_substitution_assessments_populated(tmpdb):
    seed_builtin.seed_all()
    rows = tmpdb.execute("SELECT COUNT(*) FROM substitution_assessments").fetchone()[0]
    assert rows >= len(seed_builtin.BUILTIN_SUBSTITUTION)


def test_catalyst_events_populated(tmpdb):
    seed_builtin.seed_all()
    rows = tmpdb.execute("SELECT COUNT(*) FROM catalyst_events").fetchone()[0]
    assert rows >= len(seed_builtin.BUILTIN_CATALYSTS)


def test_serenity_signals_have_prices(tmpdb):
    seed_builtin.seed_all()
    rows = tmpdb.execute(
        "SELECT * FROM serenity_signals WHERE price_at_signal > 0"
    ).fetchall()
    assert len(rows) == len(seed_builtin.BUILTIN_SERENITY_SIGNALS)


def test_follower_history_is_chronological(tmpdb):
    seed_builtin.seed_all()
    rows = tmpdb.execute(
        "SELECT follower_count FROM follower_history ORDER BY observed_at"
    ).fetchall()
    counts = [r[0] for r in rows]
    assert counts == sorted(counts)  # should be monotonically increasing
