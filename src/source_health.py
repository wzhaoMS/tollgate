"""Source-feed health tracking for the signal stack."""
from __future__ import annotations

from . import db


def record_source_status(
    source_name: str,
    *,
    source_type: str | None = None,
    ok: bool,
    error: str | None = None,
) -> None:
    db.init()
    status = "ok" if ok else "error"
    with db.connect() as cx:
        cx.execute(
            "INSERT INTO source_feed_status "
            "(source_name, source_type, last_checked_at, last_success_at, status, error_count, last_error) "
            "VALUES (?, ?, datetime('now'), CASE WHEN ? THEN datetime('now') ELSE NULL END, ?, ?, ?) "
            "ON CONFLICT(source_name) DO UPDATE SET "
            "source_type = COALESCE(excluded.source_type, source_feed_status.source_type), "
            "last_checked_at = excluded.last_checked_at, "
            "last_success_at = CASE WHEN ? THEN excluded.last_success_at ELSE source_feed_status.last_success_at END, "
            "status = excluded.status, "
            "error_count = CASE WHEN ? THEN 0 ELSE source_feed_status.error_count + 1 END, "
            "last_error = excluded.last_error",
            (source_name, source_type, ok, status, 0 if ok else 1, error, ok, ok),
        )


def stale_or_failed_sources(max_age_hours: int = 24) -> list[dict]:
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT * FROM source_feed_status WHERE status != 'ok' "
            "OR last_success_at IS NULL "
            "OR last_success_at < datetime('now', ?)",
            (f"-{max_age_hours} hours",),
        ).fetchall()
    return [dict(r) for r in rows]
