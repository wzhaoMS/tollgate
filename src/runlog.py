"""Persist pipeline run outcomes for auditability."""
from __future__ import annotations

import json
import subprocess

from . import db
from .config import ROOT


def _git_sha() -> str | None:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:  # noqa: BLE001
        return None
    if p.returncode != 0:
        return None
    return p.stdout.strip() or None


def start(command: str) -> int:
    db.init()
    with db.connect() as cx:
        cur = cx.execute(
            "INSERT INTO pipeline_runs (command, git_sha) VALUES (?, ?)",
            (command, _git_sha()),
        )
        return int(cur.lastrowid or 0)


def finish(
    run_id: int,
    *,
    status: str,
    inserted_count: int = 0,
    updated_count: int = 0,
    skipped_count: int = 0,
    error_count: int = 0,
    warnings: str | None = None,
    details: dict | None = None,
) -> None:
    db.init()
    with db.connect() as cx:
        cx.execute(
            "UPDATE pipeline_runs SET finished_at = datetime('now'), status = ?, "
            "inserted_count = ?, updated_count = ?, skipped_count = ?, error_count = ?, "
            "warnings = ?, details_json = ? WHERE id = ?",
            (
                status,
                inserted_count,
                updated_count,
                skipped_count,
                error_count,
                warnings,
                json.dumps(details or {}, sort_keys=True),
                run_id,
            ),
        )
