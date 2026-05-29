"""SQLite schema + thin DB helpers. Schema is created idempotently on init()."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator
from .config import DB_PATH

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS chokepoints (
    ticker                  TEXT PRIMARY KEY,
    chokepoint              TEXT,
    end_customer            TEXT,
    evidence_grade          TEXT CHECK(evidence_grade IN ('A','B','C','D','U')) DEFAULT 'U',
    evidence_source_url     TEXT,
    capacity                TEXT,
    demand_proxy            TEXT,
    capacity_gap_pct        REAL,
    expansion_timeline_mo   INTEGER,
    substitutes             TEXT,
    market_cap_usd          REAL,
    revenue_ttm_usd         REAL,
    ev_sales                REAL,
    next_catalyst           TEXT,
    catalyst_score          INTEGER,
    crowdedness             TEXT CHECK(crowdedness IN ('low','medium','high','unknown')) DEFAULT 'unknown',
    capital_structure_flag  TEXT DEFAULT 'unknown',
    time_to_truth_days      INTEGER,
    decision                TEXT DEFAULT 'Watch',
    notes                   TEXT,
    last_updated            TEXT DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS filings (
    accession_no    TEXT PRIMARY KEY,
    cik             TEXT,
    ticker          TEXT,
    form            TEXT,
    filed_at        TEXT,
    title           TEXT,
    url             TEXT,
    summary         TEXT,
    keyword_hits    TEXT,
    raw_json        TEXT,
    discovered_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings(ticker);
CREATE INDEX IF NOT EXISTS idx_filings_filed_at ON filings(filed_at);

CREATE TABLE IF NOT EXISTS evidence_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT,
    grade           TEXT CHECK(grade IN ('A','B','C','D')),
    source_url      TEXT,
    excerpt         TEXT,
    keywords        TEXT,
    extracted_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(ticker) REFERENCES chokepoints(ticker)
);
CREATE INDEX IF NOT EXISTS idx_evidence_ticker ON evidence_log(ticker);

CREATE TABLE IF NOT EXISTS scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT,
    scored_at       TEXT DEFAULT (datetime('now')),
    step_minus1     TEXT,
    step_0          TEXT,
    step_1          TEXT,
    step_2          TEXT,
    step_3          TEXT,
    step_4          TEXT,
    step_5          TEXT,
    step_6          TEXT,
    step_7          TEXT,
    step_8          TEXT,
    step_9          TEXT,
    step_10         TEXT,
    overall         TEXT CHECK(overall IN ('Buy','Watch','Pass','Skip')),
    notes           TEXT,
    FOREIGN KEY(ticker) REFERENCES chokepoints(ticker)
);
CREATE INDEX IF NOT EXISTS idx_scores_ticker_time ON scores(ticker, scored_at);
"""


def init(db_path: Path | None = None) -> None:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as cx:
        cx.executescript(SCHEMA)
        cx.commit()


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path or DB_PATH)
    cx = sqlite3.connect(path)
    cx.row_factory = sqlite3.Row
    try:
        yield cx
        cx.commit()
    finally:
        cx.close()


def upsert_chokepoint(cx: sqlite3.Connection, row: dict) -> None:
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "ticker")
    sql = (
        f"INSERT INTO chokepoints ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT(ticker) DO UPDATE SET {updates}"
    )
    cx.execute(sql, [row[c] for c in cols])


def insert_filing(cx: sqlite3.Connection, row: dict) -> bool:
    """Return True if a new row was inserted; False if it already existed."""
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    sql = f"INSERT OR IGNORE INTO filings ({col_list}) VALUES ({placeholders})"
    cur = cx.execute(sql, [row[c] for c in cols])
    return cur.rowcount > 0


def insert_evidence(cx: sqlite3.Connection, row: dict) -> int:
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    sql = f"INSERT INTO evidence_log ({col_list}) VALUES ({placeholders})"
    cur = cx.execute(sql, [row[c] for c in cols])
    return int(cur.lastrowid or 0)


def insert_score(cx: sqlite3.Connection, row: dict) -> int:
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    sql = f"INSERT INTO scores ({col_list}) VALUES ({placeholders})"
    cur = cx.execute(sql, [row[c] for c in cols])
    return int(cur.lastrowid or 0)


def list_tickers(cx: sqlite3.Connection) -> list[str]:
    return [r[0] for r in cx.execute("SELECT ticker FROM chokepoints ORDER BY ticker")]
