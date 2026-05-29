"""Tests for serenity_signals / follower_history / govt_awards seeders."""
from __future__ import annotations

from pathlib import Path

from src import seed_signals


def test_import_builtin_govt_awards_is_idempotent(tmpdb):
    n1 = seed_signals.import_builtin_govt()
    n2 = seed_signals.import_builtin_govt()
    assert n1 == len(seed_signals.BUILTIN_GOVT_AWARDS)
    assert n2 == 0
    rows = tmpdb.execute(
        "SELECT ticker, award_amount_usd FROM govt_awards ORDER BY ticker"
    ).fetchall()
    assert {r["ticker"] for r in rows} == {a["ticker"] for a in seed_signals.BUILTIN_GOVT_AWARDS}
    for r in rows:
        assert r["award_amount_usd"] > 0


def test_import_serenity_signals_csv(tmp_path: Path, tmpdb):
    csv = tmp_path / "s.csv"
    csv.write_text(
        "ticker,handle,tweet_id,signaled_at,source_url,signal_text,price_at_signal,follower_count\n"
        "SIVE,aleabitoreddit,123,2025-06-01T12:00:00Z,http://x/123,Sivers gap,4.10,460000\n"
        "XFAB,aleabitoreddit,124,2025-06-02T15:00:00Z,http://x/124,XFAB CHIPS,7.50,461000\n",
        encoding="utf-8",
    )
    n = seed_signals.import_serenity_signals(csv)
    assert n == 2
    row = tmpdb.execute(
        "SELECT ticker, price_at_signal, follower_count FROM serenity_signals WHERE tweet_id='123'"
    ).fetchone()
    assert row["ticker"] == "SIVE"
    assert row["price_at_signal"] == 4.10
    assert row["follower_count"] == 460000
    # Re-import is a no-op (UNIQUE on (handle, tweet_id)).
    assert seed_signals.import_serenity_signals(csv) == 0


def test_import_follower_history_csv(tmp_path: Path, tmpdb):
    csv = tmp_path / "f.csv"
    csv.write_text(
        "handle,observed_at,follower_count,source_url\n"
        "aleabitoreddit,2025-06-01T00:00:00Z,460000,http://x/a\n"
        "aleabitoreddit,2025-06-02T00:00:00Z,461000,http://x/a\n",
        encoding="utf-8",
    )
    assert seed_signals.import_follower_history(csv) == 2
    assert seed_signals.import_follower_history(csv) == 0  # PK dedup


def test_import_govt_csv_dedupes_against_builtin(tmp_path: Path, tmpdb):
    seed_signals.import_builtin_govt()
    csv = tmp_path / "g.csv"
    csv.write_text(
        "ticker,agency,program,award_amount_usd,official_url,announced_at,source_excerpt\n"
        # duplicate of XFAB built-in
        "XFAB,U.S. Department of Commerce,CHIPS and Science Act,50000000,http://x,2024-12-01,dup\n"
        # new award
        "AMD,U.S. DoE,X-Ray,12000000,http://doe,2025-01-15,new award\n",
        encoding="utf-8",
    )
    assert seed_signals.import_govt_awards(path=csv) == 1
    assert tmpdb.execute(
        "SELECT COUNT(*) FROM govt_awards WHERE ticker='AMD'"
    ).fetchone()[0] == 1


def test_import_missing_csv_returns_zero(tmp_path: Path, tmpdb):
    assert seed_signals.import_serenity_signals(tmp_path / "nope.csv") == 0
    assert seed_signals.import_follower_history(tmp_path / "nope.csv") == 0
    assert seed_signals.import_govt_awards(path=tmp_path / "nope.csv") == 0
