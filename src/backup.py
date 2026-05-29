"""Timestamped SQLite backups using the online backup API + gzip.

Run ``py -m src.cli backup`` (also called automatically at the start of
``all`` so we always have a snapshot before mutations). Backups are written to
``data/backups/playbook-YYYYmmdd-HHMMSS.db.gz`` and older copies pruned to the
configured retention count.
"""
from __future__ import annotations

import gzip
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR, DB_PATH

BACKUP_DIR = DATA_DIR / "backups"
RETENTION = 14  # keep ~2 weeks of daily snapshots


def _candidate_path(now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return BACKUP_DIR / f"playbook-{stamp}.db.gz"


def create_backup(db_path: Path | None = None, dest: Path | None = None) -> Path | None:
    """Snapshot ``db_path`` to a gzipped file and return the resulting path.

    Returns ``None`` if the source DB does not exist yet.
    """
    src = Path(db_path or DB_PATH)
    if not src.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(dest or _candidate_path())
    tmp = out.with_suffix(out.suffix + ".tmp")
    # Use sqlite's online backup API for a consistent snapshot, then gzip it.
    raw = tmp.with_suffix(".raw")
    live = sqlite3.connect(src)
    snap = sqlite3.connect(raw)
    try:
        live.backup(snap)
    finally:
        snap.close()
        live.close()
    with raw.open("rb") as r, gzip.open(tmp, "wb") as w:
        shutil.copyfileobj(r, w)
    raw.unlink(missing_ok=True)
    tmp.replace(out)
    _prune()
    return out


def _prune(keep: int = RETENTION) -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(BACKUP_DIR.glob("playbook-*.db.gz"))
    excess = backups[:-keep] if keep > 0 else []
    for old in excess:
        old.unlink(missing_ok=True)
    return excess


def main() -> None:
    out = create_backup()
    if out:
        print(f"backup: wrote {out} ({out.stat().st_size} bytes)")
    else:
        print("backup: source DB missing; nothing to do")


if __name__ == "__main__":
    main()
