# Serenity-Killer Playbook App Audit

Date: 2026-05-29
Auditor: GitHub Copilot
Scope: codebase, live Streamlit dashboard, local SQLite data state, CLI health checks, tests, lint, and CI config.

## Goal Context

I checked memory first. The persistent memory currently describes an older Codex/Copilot bridge project, not this app. For this audit, the app goal was inferred from the repo docs and current implementation:

Serenity-Killer Playbook is a local OSINT investing pipeline for AI/semiconductor supply-chain chokepoints. It should harvest EDGAR filings, full filing bodies, Form 4 insider transactions, prices, tweets, and customer-page diffs; convert those sources into deterministic evidence; score tickers against an 11-step playbook; and expose the state through a Streamlit dashboard and daily digest. The design goal is decision hygiene: avoid weak evidence, crowd contamination, poor liquidity, bad capital structure, and late/contaminated narratives.

## Executive Verdict

Current state: production-capable MVP, but not yet production-grade.

The core app is much stronger than before: EDGAR per-ticker harvesting is fixed, Form 4 collection works, full 10-K body fetch now unwraps EDGAR inline-XBRL viewer URLs, step_4 produces real government-backstop signals, CI exists, lint is clean, and tests pass. The biggest remaining risks are operational: the live `doctor` check currently fails because the real `.env` still uses the placeholder EDGAR user agent; read/report flows mutate the scoring table; many network failures are swallowed as prints; the dashboard can run long mutating jobs without locking/auth/audit trail; and the LLM evidence pipeline is not yet populating `evidence_log`.

## Live Validation Snapshot

- Git status before audit file: clean at `11a8a40` on `origin/main`.
- `py -m src.cli doctor`: failed with 1 error, `EDGAR_USER_AGENT` placeholder in the live environment.
- `py -m ruff check .`: passed.
- `py -m pytest -q`: 35 passed.
- Coverage after installing `pytest-cov`: 29% total. Scoring is well covered at 93%; CLI/dashboard/digest/doctor/nitter/Alpaca paths are mostly or entirely uncovered.
- Coverage run emitted repeated `ResourceWarning: unclosed database` warnings during test cleanup.
- Live DB state:
  - chokepoints: 27
  - filings: 1433
  - filings with full body text: 47
  - government-flagged filings: 34
  - insider transactions: 981
  - prices: 1631
  - evidence_log: 0
  - tweets: 268
  - page_snapshots: 8
  - latest score rows: 27
  - latest overall distribution: Buy 2, Watch 15, Pass 10
- Streamlit dashboard was live at `http://localhost:8501/`, but showed a `File change. Rerun` banner and stale KPI distribution relative to the DB snapshot.

## P0 / Blockers Before Real Production

### 1. Live EDGAR configuration fails the health check

Evidence:
- `src/config.py:33-35` defaults `EDGAR_USER_AGENT` to `serenity-killer-playbook contact@example.com`.
- `src/doctor.py:28-35` correctly treats the placeholder as an error.
- Live `py -m src.cli doctor` failed on this exact check.

Why it matters:
SEC Fair Access requires a real contact user agent. A placeholder can cause throttling/blocking, which makes the pipeline silently stale or partially empty.

Recommendation:
Set the real `.env` value to a contact-bearing user agent and make `cmd_all` call `doctor.run()` before network work. If `doctor` returns non-zero, abort the daily pipeline. Keep `.env.example:8` as the safe example value, but never rely on the code default for live runs.

## P1 / High Priority Findings

### 2. Scheduled daily pipeline likely fails unless Task Scheduler starts in the repo directory

Evidence:
- `RUN.md:84-85` schedules `py -m src.cli all` without setting a working directory.
- A recent terminal command run from `C:\Users\zhaow` failed when importing `src` outside the repo.

Why it matters:
The current scheduler guidance is fragile. A daily job may fail even though the same command works in an already-cd'd terminal.

Recommendation:
Update the scheduled task to set `Start in` to `C:\Users\zhaow\serenity-killer-playbook`, or run a wrapper script that does `Set-Location` before invoking the CLI. Better: install the package (`pip install -e .`) and schedule the console script `serenity all` from a controlled virtualenv.

### 3. Read/report flows mutate scoring history

Evidence:
- `src/scoring.py:232-245` computes all rows and always inserts a new score row via `db.insert_score`.
- `src/digest.py:79` calls `scoring.score_all()` while rendering a digest.
- `src/alpaca_paper.py:68` and `src/alpaca_paper.py:94` call `scoring.score_all()` while syncing positions.

Why it matters:
Digest generation and paper sync should not create new score history as a side effect. This inflates `scores`, changes the "latest" state, makes audit trails noisy, and can hide when the actual scoring step last ran.

Recommendation:
Split scoring into two APIs:
- `compute_all(cx) -> list[dict]` with no writes.
- `persist_scores(scores)` or `score_all(persist=True)` for the explicit `score` command.
Then make digest and paper sync consume the latest persisted score rows unless explicitly asked to re-score.

### 4. Evidence extraction is not yet feeding step_1 in production

Evidence:
- Live DB has `evidence_log = 0`.
- `src/enrich/filing_text.py:123-138` enriches only the most recent 5 filings by default and catches failures as prints.
- `src/enrich/filing_text.py:31` has its own filing-text fetcher instead of reusing the newer, fixed primary-document resolver in `src/enrich/filing_full.py`.

Why it matters:
The app's thesis depends on evidence grade discipline. If `evidence_log` is empty, step_1 relies mainly on curated seed data instead of harvested evidence. That weakens the "discovered fact-change" promise.

Recommendation:
Unify full-text fetching behind `filing_full._resolve_primary_doc`, add an `enrichment_status` or processed table keyed by accession, and run a deterministic backlog until each relevant filing is either enriched, skipped with reason, or failed with retry count. Add a dashboard metric for `evidence_log` count and stale/unprocessed filings.

### 5. Network and parsing failures are often swallowed, so `all` can look successful after partial failure

Evidence:
- Broad catches print and continue in `src/scrapers/edgar.py:196`, `src/enrich/filing_full.py:145`, `src/enrich/filing_text.py:138`, `src/scrapers/insider_form4.py:151/164/189`, `src/scrapers/nitter_x.py:66/112`, `src/scrapers/customer_diff.py:65`, and `src/scrapers/yf_prices.py:131`.
- `src/cli.py:147-160` runs the daily pipeline step-by-step but does not aggregate failures into a non-zero exit.

Why it matters:
This is acceptable for exploration, but production jobs need a reliable success/failure signal. Today, a broken Nitter mirror, blocked EDGAR user agent, or parsing regression can degrade the data without failing the run.

Recommendation:
Introduce a `RunResult` shape for every command: `inserted`, `updated`, `skipped`, `errors`, `warnings`, `critical`. Have `cmd_all` aggregate those and exit non-zero on critical failures. Persist one row per run in a new `pipeline_runs` table with start/end, counts, errors, and git SHA.

### 6. Dashboard can trigger mutating jobs without locking, auth, or audit trail

Evidence:
- `src/dashboard.py:98` runs CLI commands via `subprocess.run`.
- Buttons at `src/dashboard.py:111-129` can refresh prices, re-score, sync paper portfolio, and ask for a weekly brief.

Why it matters:
The implementation uses argument lists, so shell injection is not the main issue. The risk is operational: concurrent clicks can overlap long jobs; there is no lock; failures are truncated to the last 30 lines; and if Streamlit is exposed beyond localhost, anyone with access can trigger mutating actions.

Recommendation:
Keep the dashboard bound to localhost by default, add a process lock around pipeline actions, record dashboard-triggered runs in `pipeline_runs`, and gate broker-affecting actions behind an explicit confirmation. If the app ever leaves localhost, add authentication immediately.

### 7. Paper trading sync can place orders from a scoring side effect and has no sizing guard

Evidence:
- `src/alpaca_paper.py:57-124` opens/closes positions directly from current score decisions.
- Comment notes "1 ticker = 1 share" and that real sizing is not wired in.

Why it matters:
Even in paper mode, this is the bridge from research signal to orders. It needs stronger safety semantics before a real broker adapter is used.

Recommendation:
Add a dry-run default, explicit `--execute`, max order value, allowlist, no-trade-if-data-stale check, and a trade decision log. Use latest persisted scores, not freshly inserted scores from `score_all()`.

## P2 / Medium Priority Findings

### 8. Dashboard state can be stale or misleading

Evidence:
- Browser displayed `File change. Rerun` and dashboard KPIs showed Buy 8 / Watch 7 / Pass 12, while the live DB latest scores were Buy 2 / Watch 15 / Pass 10.
- `src/dashboard.py:32-87` caches SQL reads for 60 seconds.
- `src/dashboard.py:54` loads only 50 filings.
- `src/dashboard.py:281` filters drill-down filings by title containing the ticker, not by the `ticker` column.

Why it matters:
An investing dashboard has to be trusted at a glance. Stale or incorrectly filtered views will cause the operator to miss evidence or act on outdated scores.

Recommendation:
Show the latest `scored_at`, latest pipeline run time, and DB file mtime in the header. Replace title-based filing drill-down with `WHERE ticker = ?`. Load drill-down filings per ticker on demand instead of filtering the last 50 global filings.

### 9. Top-movers chart has rendering warnings and visual control issues

Evidence:
- Browser console reported Vega warnings: infinite extents and scale-binding warnings.
- Screenshot shows selected ticker chips in the multiselect as red blocks with labels hard to read.
- `src/dashboard.py:203-219` builds a Streamlit line chart after optional `np.log10` transformation.

Why it matters:
The chart is a key contamination/momentum view. If selected tickers are unreadable or the chart emits invalid extents, the UI becomes harder to trust.

Recommendation:
Before charting, coerce `date` to datetime, drop non-positive/NaN normalized values before log scaling, and use an explicit Altair chart with stable color scale and tooltip. Re-check the multiselect styling after rerun; if Streamlit theme CSS is causing unreadable chips, override the theme or use a compact checkbox/table selector.

### 10. Full-body filing coverage is still narrow

Evidence:
- Live DB: only 47 / 1433 filings have `length(summary) >= 500`.
- By form: 8-K has 7 full bodies, 10-K has 40, 10-Q has 0.
- `src/cli.py:153-154` daily `all` currently fetches 60 8-K and 40 10-K candidates per run.
- `src/enrich/filing_full.py:117-152` fetches only rows where `summary` is null or shorter than 500.

Why it matters:
step_4 is now proven, but the full text backlog remains mostly unprocessed. 10-Qs may contain fresh risk/capex/customer disclosures that never get scanned.

Recommendation:
Add a `filing_fetch_status` table or columns (`body_fetched_at`, `body_fetch_status`, `body_fetch_error`, `body_sha256`, `keyword_scan_version`). Process by priority: newest 8-K, newest 10-Q, newest 10-K, then older backlog. Re-scan when the keyword dictionary changes.

### 11. Test coverage is concentrated in pure logic, not production adapters

Evidence:
- Coverage total: 29%.
- 0% coverage: `src/cli.py`, `src/dashboard.py`, `src/digest.py`, `src/doctor.py`, `src/scrapers/nitter_x.py`, `src/alpaca_paper.py`, `src/enrich/filing_text.py`, `src/brief.py`, `src/backtest.py`.
- Strong coverage: `src/scoring.py` at 93%, `src/pair_trade.py` at 88%, `src/paper.py` at 84%.

Why it matters:
The riskiest production behavior is in network adapters, CLI orchestration, dashboard actions, and broker/digest paths. These are currently the least tested.

Recommendation:
Add mocked-network tests for EDGAR, Form 4, Nitter, customer diff, yfinance, Telegram, and Alpaca. Add CLI tests around `doctor`, `fulltext --form`, `harvest --ticker`, and `all` failure aggregation. Add a Streamlit smoke test or at least tests for loader SQL functions.

### 12. Local environment does not match declared dev extras by default

Evidence:
- `pyproject.toml:29` declares `pytest-cov`, but local coverage failed until `pytest-cov` was manually installed.

Why it matters:
Developers can believe they are running the full dev toolchain while missing plugins. CI installs `.[dev]`, but local docs still say `pip install -r requirements.txt`.

Recommendation:
Update `RUN.md` setup to prefer `py -m pip install -e ".[dev]"`. Keep `requirements.txt` only if it is intentionally runtime-only.

### 13. SQLite has no migration or backup story

Evidence:
- `src/db.py` creates schema via `CREATE TABLE IF NOT EXISTS`, but there is no schema version or migration table.
- The app depends on local `data/playbook.db`, which is gitignored.

Why it matters:
As soon as columns are added (run logs, fetch status, scan version), existing DBs need safe migration. Local DB loss also means losing evidence history, positions, and snapshots.

Recommendation:
Add `schema_migrations` and small ordered migration scripts. Enable WAL mode. Add a daily backup command that copies the DB to timestamped compressed backups before `all` mutates it.

### 14. Nitter scraping is inherently brittle

Evidence:
- `src/scrapers/nitter_x.py:24-30` hardcodes public Nitter mirrors.
- `_try_fetch` falls through mirrors and prints a single final error.

Why it matters:
Nitter mirrors frequently disappear or throttle. Treating this as a core signal source without per-handle status will create silent blind spots.

Recommendation:
Record per-handle fetch status and last success time. Consider an official X API path, a paid scrape provider, or treating Nitter as opportunistic only. Show stale handles in the dashboard.

### 15. Docs are slightly behind implementation

Evidence:
- `README.md` still says the seed database has 9 tickers, but the live DB has 27.
- `RUN.md` says real broker integration and backtesting are planned, while `alpaca_paper.py` and `backtest.py` now exist.

Why it matters:
Operational docs are part of production quality. Stale docs are how correct code gets run incorrectly.

Recommendation:
Refresh README/RUN after the next code hardening pass: current setup, current scheduler, dashboard caveats, current data counts, and exact production checklist.

## Strengths Worth Keeping

- The app now has a clear package/CI base (`pyproject.toml`, GitHub Actions, ruff, pytest).
- EDGAR exact-form filtering and per-ticker targeting address the major prefix-match trap.
- Full filing body fetch now avoids EDGAR inline-XBRL viewer shells.
- step_4 is deterministic and backed by persisted filing keyword hits.
- Scoring favors `unknown` over false certainty, which fits the stated investment-discipline goal.
- SQLite schema is simple and inspectable; this is good for a single-user research pipeline.
- Streamlit dashboard is already useful as an operator console, especially with price/scoring/positions in one place.

## Recommended Next Sprint

1. Fix live `.env` and make `all` abort if `doctor` fails.
2. Fix scheduler command/working directory and document the real production command.
3. Refactor scoring into compute-only vs persist APIs.
4. Add `pipeline_runs` and structured result objects for every CLI command.
5. Unify filing text fetchers and build an enrichment backlog until `evidence_log` is non-zero.
6. Fix dashboard drill-down to query by ticker and show data freshness timestamps.
7. Add network-mocked tests for doctor, CLI, EDGAR body fetch, dashboard loaders, digest, and Alpaca dry-run.

## Production Readiness Rating

MVP research workstation: 8/10.

Unattended daily local production: 6/10 until `doctor` gates `all`, scheduling is fixed, partial failures become non-zero, and scoring side effects are removed.

Shared/team/broker-connected production: 3/10 until auth, locking, audit logs, migrations, backups, explicit trade safety gates, and stronger adapter tests are added.