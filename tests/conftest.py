"""Shared pytest fixtures.

All tests run against a throwaway SQLite database. We point both the ``db``
module's default path and ``config.DB_PATH`` at a temp file so any code that
calls ``db.connect()`` / ``db.init()`` without an explicit path is isolated.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def tmpdb(tmp_path, monkeypatch):
    """Initialise a fresh schema in a temp DB and return a live connection."""
    from src import config, db

    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init(path)

    cx = sqlite3.connect(path)
    cx.row_factory = sqlite3.Row
    yield cx
    cx.close()
