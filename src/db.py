"""SQLite schema + thin DB helpers. Schema is created idempotently on init()."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH

# Ordered list of (version, sql) migrations applied after the base SCHEMA.
# Each migration is wrapped in its own transaction and recorded in
# ``schema_migrations``. Migrations must be idempotent-safe (use IF NOT EXISTS
# / IF NOT EXISTS column probes) so re-running init() on a partially-migrated
# DB is safe.
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker              TEXT PRIMARY KEY,
            measured_at         TEXT DEFAULT (datetime('now')),
            pb                  REAL,
            pe                  REAL,
            ev_sales            REAL,
            segment_growth_pct  REAL,
            sell_side_analysts  INTEGER,
            region              TEXT,
            source_url          TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fundamentals_segment_growth
            ON fundamentals(segment_growth_pct);
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS potential_acquirers (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            target_ticker           TEXT NOT NULL,
            acquirer_name           TEXT NOT NULL,
            acquirer_ticker         TEXT,
            strategic_value_usd     REAL NOT NULL,
            evidence_url            TEXT,
            notes                   TEXT,
            recorded_at             TEXT DEFAULT (datetime('now')),
            UNIQUE(target_ticker, acquirer_name)
        );
        CREATE INDEX IF NOT EXISTS idx_potential_acquirers_target
            ON potential_acquirers(target_ticker);
        """,
    ),
    (
        3,
        """
        CREATE TABLE IF NOT EXISTS capacity_quarterly (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker                  TEXT NOT NULL,
            quarter                 TEXT NOT NULL,
            supply_units            REAL,
            demand_units            REAL,
            gap_pct                 REAL,
            unit_label              TEXT DEFAULT 'units',
            price_power             TEXT CHECK(price_power IN
                ('very_high','high','neutral','low','collapse','unknown')) DEFAULT 'unknown',
            capex_planned_usd       REAL,
            expansion_online_date   TEXT,
            source_url              TEXT,
            assumptions             TEXT,
            updated_at              TEXT DEFAULT (datetime('now')),
            UNIQUE(ticker, quarter)
        );
        CREATE INDEX IF NOT EXISTS idx_capacity_quarterly_ticker
            ON capacity_quarterly(ticker);
        """,
    ),
    (
        4,
        """
        CREATE TABLE IF NOT EXISTS customer_supplier_pages (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_ticker     TEXT NOT NULL,
            page_url            TEXT NOT NULL,
            page_label          TEXT,
            last_snapshot_at    TEXT,
            last_content_sha256 TEXT,
            removed_names       TEXT,
            added_names         TEXT,
            check_interval_hrs  INTEGER DEFAULT 24,
            enabled             INTEGER DEFAULT 1,
            created_at          TEXT DEFAULT (datetime('now')),
            UNIQUE(customer_ticker, page_url)
        );
        CREATE INDEX IF NOT EXISTS idx_csp_customer
            ON customer_supplier_pages(customer_ticker);
        """,
    ),
    (
        5,
        """
        CREATE TABLE IF NOT EXISTS governance_events (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker              TEXT NOT NULL,
            event_type          TEXT NOT NULL,
            person_name         TEXT,
            role                TEXT,
            prior_ma_exp        INTEGER DEFAULT 0,
            source_url          TEXT,
            event_date          TEXT,
            notes               TEXT,
            discovered_at       TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_governance_events_ticker
            ON governance_events(ticker);

        CREATE TABLE IF NOT EXISTS customer_warrants (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            issuer_ticker       TEXT NOT NULL,
            holder_name         TEXT NOT NULL,
            holder_ticker       TEXT,
            warrant_shares      REAL,
            exercise_price_usd  REAL,
            filing_type         TEXT,
            filing_url          TEXT,
            announced_at        TEXT,
            notes               TEXT,
            discovered_at       TEXT DEFAULT (datetime('now')),
            UNIQUE(issuer_ticker, holder_name)
        );
        CREATE INDEX IF NOT EXISTS idx_customer_warrants_issuer
            ON customer_warrants(issuer_ticker);

        CREATE TABLE IF NOT EXISTS research_papers (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker              TEXT,
            theme               TEXT,
            title               TEXT NOT NULL,
            authors             TEXT,
            paper_url           TEXT,
            abstract            TEXT,
            relevance_score     REAL,
            published_at        TEXT,
            discovered_at       TEXT DEFAULT (datetime('now')),
            UNIQUE(paper_url)
        );
        CREATE INDEX IF NOT EXISTS idx_research_papers_ticker
            ON research_papers(ticker);

        CREATE TABLE IF NOT EXISTS signal_feed_alerts (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type         TEXT NOT NULL,
            source_name         TEXT,
            ticker              TEXT,
            keyword_matched     TEXT,
            title               TEXT,
            url                 TEXT,
            snippet             TEXT,
            alert_priority      TEXT CHECK(alert_priority IN
                ('critical','high','medium','low')) DEFAULT 'medium',
            acknowledged        INTEGER DEFAULT 0,
            created_at          TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_signal_feed_alerts_ticker
            ON signal_feed_alerts(ticker);
        CREATE INDEX IF NOT EXISTS idx_signal_feed_alerts_unack
            ON signal_feed_alerts(acknowledged, created_at);
        """,
    ),
]

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

CREATE TABLE IF NOT EXISTS prices (
    ticker          TEXT,
    date            TEXT,
    close           REAL,
    volume          REAL,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS contamination (
    ticker                  TEXT PRIMARY KEY,
    measured_at             TEXT DEFAULT (datetime('now')),
    last_close              REAL,
    pct_change_5d           REAL,
    pct_change_20d          REAL,
    volume_ratio_20d        REAL,
    crowd_flag              TEXT CHECK(crowd_flag IN ('low','medium','high','unknown')) DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS insider_txns (
    accession_no    TEXT,
    ticker          TEXT,
    filer_name      TEXT,
    relation        TEXT,
    txn_date        TEXT,
    txn_code        TEXT,
    shares          REAL,
    price           REAL,
    dollar_amount   REAL,
    url             TEXT,
    discovered_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (accession_no, filer_name, txn_date, txn_code)
);
CREATE INDEX IF NOT EXISTS idx_insider_ticker ON insider_txns(ticker);

CREATE TABLE IF NOT EXISTS insider_option_events (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                  TEXT NOT NULL,
    insider_name            TEXT,
    role                    TEXT,
    expiry_date             TEXT NOT NULL,
    shares                  REAL,
    estimated_value_usd     REAL,
    status                  TEXT CHECK(status IN ('open','exercised','expired','unknown')) DEFAULT 'open',
    source_url              TEXT,
    discovered_at           TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_option_events_ticker_expiry ON insider_option_events(ticker, expiry_date);

CREATE TABLE IF NOT EXISTS tweets (
    tweet_id        TEXT PRIMARY KEY,
    handle          TEXT,
    posted_at       TEXT,
    text            TEXT,
    tickers         TEXT,
    url             TEXT,
    discovered_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tweets_handle_time ON tweets(handle, posted_at);

CREATE TABLE IF NOT EXISTS page_snapshots (
    url             TEXT,
    snapshot_at     TEXT DEFAULT (datetime('now')),
    content_sha256  TEXT,
    char_len        INTEGER,
    diff_lines      INTEGER,
    PRIMARY KEY (url, snapshot_at)
);
CREATE INDEX IF NOT EXISTS idx_pages_url_time ON page_snapshots(url, snapshot_at);

CREATE TABLE IF NOT EXISTS positions (
    ticker          TEXT PRIMARY KEY,
    opened_at       TEXT DEFAULT (datetime('now')),
    cost_basis      REAL,
    shares          REAL,
    high_water      REAL,
    last_price      REAL,
    pnl_pct         REAL,
    closed_at       TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    command         TEXT NOT NULL,
    started_at      TEXT DEFAULT (datetime('now')),
    finished_at     TEXT,
    status          TEXT CHECK(status IN ('running','ok','warn','error')) DEFAULT 'running',
    git_sha         TEXT,
    inserted_count  INTEGER DEFAULT 0,
    updated_count   INTEGER DEFAULT 0,
    skipped_count   INTEGER DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    warnings        TEXT,
    details_json    TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);

CREATE TABLE IF NOT EXISTS signal_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT,
    source_type     TEXT,
    source_url      TEXT,
    observed_at     TEXT DEFAULT (datetime('now')),
    event_date      TEXT,
    title           TEXT,
    summary         TEXT,
    evidence_grade  TEXT CHECK(evidence_grade IN ('A','B','C','D','U')) DEFAULT 'U',
    consensus_state TEXT CHECK(consensus_state IN ('undiscovered','partial','consensus','unknown')) DEFAULT 'unknown',
    raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_signal_events_ticker_time ON signal_events(ticker, observed_at);

CREATE TABLE IF NOT EXISTS serenity_signals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    handle              TEXT DEFAULT 'aleabitoreddit',
    tweet_id            TEXT,
    signaled_at         TEXT NOT NULL,
    source_url          TEXT,
    signal_text         TEXT,
    price_at_signal     REAL,
    price_checked_at    TEXT,
    follower_count      INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(handle, tweet_id)
);
CREATE INDEX IF NOT EXISTS idx_serenity_signals_ticker_time ON serenity_signals(ticker, signaled_at);

CREATE TABLE IF NOT EXISTS supplier_relationships (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_ticker     TEXT NOT NULL,
    customer_name       TEXT,
    customer_ticker     TEXT,
    source_accession_no TEXT,
    source_url          TEXT,
    source_type         TEXT,
    evidence_grade      TEXT CHECK(evidence_grade IN ('A','B','C','D','U')) DEFAULT 'U',
    relationship_type   TEXT,
    phrase              TEXT,
    direction           TEXT CHECK(direction IN ('customer_to_supplier','supplier_to_customer','unknown')) DEFAULT 'unknown',
    confidence          REAL,
    verified_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_supplier_relationships_supplier ON supplier_relationships(supplier_ticker);
CREATE INDEX IF NOT EXISTS idx_supplier_relationships_customer ON supplier_relationships(customer_ticker, customer_name);

CREATE TABLE IF NOT EXISTS capacity_models (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                  TEXT NOT NULL,
    period                  TEXT NOT NULL,
    supply_units            REAL,
    demand_units            REAL,
    gap_pct                 REAL,
    expansion_timeline_mo   INTEGER,
    source_url              TEXT,
    assumptions             TEXT,
    updated_at              TEXT DEFAULT (datetime('now')),
    UNIQUE(ticker, period)
);
CREATE INDEX IF NOT EXISTS idx_capacity_models_ticker_period ON capacity_models(ticker, period);

CREATE TABLE IF NOT EXISTS substitution_assessments (
    id                                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                              TEXT NOT NULL,
    substitute_materials                TEXT,
    substitute_suppliers                TEXT,
    customer_self_build_risk            TEXT,
    short_term_non_substitutable_count  INTEGER,
    status                              TEXT CHECK(status IN ('pass','watch','fail','unknown')) DEFAULT 'unknown',
    source_url                          TEXT,
    notes                               TEXT,
    assessed_at                         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_substitution_ticker_time ON substitution_assessments(ticker, assessed_at);

CREATE TABLE IF NOT EXISTS govt_awards (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    agency              TEXT,
    program             TEXT,
    award_amount_usd    REAL,
    official_url        TEXT,
    announced_at        TEXT,
    source_excerpt      TEXT,
    verified_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_govt_awards_ticker_amount ON govt_awards(ticker, award_amount_usd);

CREATE TABLE IF NOT EXISTS float_short_interest (
    ticker                  TEXT PRIMARY KEY,
    measured_at             TEXT DEFAULT (datetime('now')),
    float_shares            REAL,
    short_interest_pct      REAL,
    avg_dollar_volume       REAL,
    intended_position_usd   REAL,
    days_to_exit            REAL,
    source_url              TEXT
);

CREATE TABLE IF NOT EXISTS catalyst_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    event_date      TEXT NOT NULL,
    event_type      TEXT,
    description     TEXT,
    falsifiable     INTEGER DEFAULT 1,
    probability     REAL,
    source_url      TEXT,
    status          TEXT CHECK(status IN ('planned','confirmed','missed','done','cancelled')) DEFAULT 'planned',
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_catalyst_events_ticker_date ON catalyst_events(ticker, event_date);

CREATE TABLE IF NOT EXISTS position_sizing_decisions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                  TEXT NOT NULL,
    decided_at              TEXT DEFAULT (datetime('now')),
    p_win                   REAL,
    avg_gain_pct            REAL,
    p_loss                  REAL,
    avg_loss_pct            REAL,
    kelly_fraction          REAL,
    quarter_kelly_pct       REAL,
    capped_position_pct     REAL,
    dollar_amount           REAL,
    constraints_json        TEXT,
    decision                TEXT
);
CREATE INDEX IF NOT EXISTS idx_position_sizing_ticker_time ON position_sizing_decisions(ticker, decided_at);

CREATE TABLE IF NOT EXISTS theme_exposures (
    theme               TEXT PRIMARY KEY,
    measured_at         TEXT DEFAULT (datetime('now')),
    gross_exposure_pct  REAL,
    net_exposure_pct    REAL,
    cap_pct             REAL DEFAULT 15.0,
    status              TEXT CHECK(status IN ('ok','watch','breach','unknown')) DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS follower_history (
    handle          TEXT NOT NULL,
    observed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    follower_count  INTEGER NOT NULL,
    source_url      TEXT,
    PRIMARY KEY (handle, observed_at)
);

CREATE TABLE IF NOT EXISTS pair_trade_watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    theme           TEXT,
    long_ticker     TEXT NOT NULL,
    short_ticker    TEXT NOT NULL,
    opened_at       TEXT DEFAULT (datetime('now')),
    closed_at       TEXT,
    entry_spread_pct REAL,
    current_spread_pct REAL,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_pair_watchlist_open ON pair_trade_watchlist(closed_at, theme);

CREATE TABLE IF NOT EXISTS pair_trade_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id         INTEGER,
    measured_at          TEXT DEFAULT (datetime('now')),
    long_price           REAL,
    short_price          REAL,
    spread_pct           REAL,
    pnl_pct              REAL,
    FOREIGN KEY(watchlist_id) REFERENCES pair_trade_watchlist(id)
);
CREATE INDEX IF NOT EXISTS idx_pair_snapshots_watchlist_time ON pair_trade_snapshots(watchlist_id, measured_at);

CREATE TABLE IF NOT EXISTS ma_floor_estimates (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                  TEXT NOT NULL,
    estimated_floor_usd     REAL,
    current_market_cap_usd  REAL,
    acquirers               TEXT,
    strategic_value_notes   TEXT,
    source_url              TEXT,
    assessed_at             TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ma_floor_ticker_time ON ma_floor_estimates(ticker, assessed_at);

CREATE TABLE IF NOT EXISTS consensus_metrics (
    ticker                  TEXT PRIMARY KEY,
    measured_at             TEXT DEFAULT (datetime('now')),
    truth_score             REAL,
    consensus_score         REAL,
    analyst_coverage_count  INTEGER,
    media_mentions_30d      INTEGER,
    social_mentions_30d     INTEGER,
    status                  TEXT CHECK(status IN ('hidden_truth','emerging','consensus','unproven','unknown')) DEFAULT 'unknown',
    source_url              TEXT
);

CREATE TABLE IF NOT EXISTS source_feed_status (
    source_name     TEXT PRIMARY KEY,
    source_type     TEXT,
    last_checked_at TEXT,
    last_success_at TEXT,
    status          TEXT CHECK(status IN ('ok','warn','error','unknown')) DEFAULT 'unknown',
    error_count     INTEGER DEFAULT 0,
    last_error      TEXT
);

CREATE TABLE IF NOT EXISTS exit_plans (
    ticker                          TEXT PRIMARY KEY,
    created_at                      TEXT DEFAULT (datetime('now')),
    stop_loss_pct                   REAL DEFAULT -40.0,
    take_profit_1_pct               REAL DEFAULT 200.0,
    take_profit_1_sell_pct          REAL DEFAULT 33.3333,
    take_profit_1_trailing_stop_pct REAL DEFAULT -25.0,
    take_profit_2_pct               REAL DEFAULT 500.0,
    take_profit_2_sell_pct          REAL DEFAULT 50.0,
    take_profit_2_trailing_stop_pct REAL DEFAULT -15.0,
    stale_months                    INTEGER DEFAULT 18,
    analyst_coverage_trim_threshold INTEGER DEFAULT 3,
    capacity_gap_exit_pct           REAL DEFAULT -5.0,
    notes                           TEXT
);
"""


def init(db_path: Path | None = None) -> None:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as cx:
        cx.executescript(SCHEMA)
        cx.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
        )
        try:
            cx.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass  # WAL may be unavailable on some filesystems; not fatal
        applied = {row[0] for row in cx.execute("SELECT version FROM schema_migrations")}
        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            cx.executescript(sql)
            cx.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
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
