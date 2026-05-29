"""Tests for schema migrations table, WAL mode, and DB backups."""
from __future__ import annotations

import gzip
import sqlite3

from src import backup, db


def test_init_creates_schema_migrations_and_enables_wal(tmpdb):
    rows = tmpdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchall()
    assert rows, "schema_migrations table should exist after init()"
    mode = tmpdb.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() in {"wal", "memory"}  # WAL or fallback if unsupported


def test_init_applies_pending_migrations_once(tmp_path, monkeypatch):
    from src import config

    path = tmp_path / "mig.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(
        db,
        "MIGRATIONS",
        [(1, "CREATE TABLE IF NOT EXISTS _mig_demo(id INTEGER PRIMARY KEY)")],
    )
    db.init(path)
    db.init(path)  # second call must not re-apply

    cx = sqlite3.connect(path)
    versions = [r[0] for r in cx.execute("SELECT version FROM schema_migrations")]
    tables = [r[0] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    cx.close()
    assert versions.count(1) == 1
    assert "_mig_demo" in tables


def test_create_backup_writes_gzipped_snapshot(tmp_path, monkeypatch):
    from src import config

    src_path = tmp_path / "playbook.db"
    monkeypatch.setattr(db, "DB_PATH", src_path)
    monkeypatch.setattr(config, "DB_PATH", src_path)
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    db.init(src_path)

    out = backup.create_backup(src_path)
    assert out is not None
    assert out.exists()
    assert out.suffix == ".gz"
    # Gzipped magic header
    with gzip.open(out, "rb") as fh:
        head = fh.read(16)
    assert head.startswith(b"SQLite format 3")


def test_create_backup_no_db_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    assert backup.create_backup(tmp_path / "missing.db") is None
