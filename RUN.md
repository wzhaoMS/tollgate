# Run guide

## One-time setup

```powershell
cd C:\Users\zhaow\serenity-killer-playbook
py -m pip install -e ".[dev]"          # installs runtime + pytest/ruff
copy .env.example .env                 # then edit EDGAR_USER_AGENT etc.
py -m src.cli init                     # creates SQLite schema + WAL + migrations
py -m src.cli seed                     # loads chokepoint seed rows
py -m src.cli doctor                   # MUST be green before scheduling
```

## Daily commands

```powershell
# Full pipeline (doctor -> backup -> seed -> prices -> harvest -> fulltext -> relationships -> insider -> tweets -> diffwatch -> enrich -> score -> paper -> monitor -> digest)
py -m src.cli all                      # aborts early if doctor fails

# Or step by step (useful for debugging)
py -m src.cli prices
py -m src.cli harvest
py -m src.cli fulltext --form 8-K --limit 60
py -m src.cli fulltext --form 10-K --limit 40
py -m src.cli relationships            # customer-filing reverse verification -> supplier_relationships
py -m src.cli insider
py -m src.cli tweets
py -m src.cli diffwatch
py -m src.cli enrich
py -m src.cli score
py -m src.cli pairs
py -m src.cli pairwatch --snapshot
py -m src.cli monitor
py -m src.cli exitplans
py -m src.cli digest
```

## Position sizing

```powershell
# Compute and persist a Kelly-lite sizing decision; paper sync will use it.
py -m src.cli size TST --account 100000 --p-win 60 --avg-gain 100 --avg-loss 30
```

`alpaca_paper` / local paper sync reads the latest row from
`position_sizing_decisions` per ticker and translates `dollar_amount` into a
share count using the latest close price. If no sizing decision exists it
falls back to 1 share (the legacy default).

## Backups

`py -m src.cli all` snapshots `data\playbook.db` to
`data\backups\playbook-YYYYmmdd-HHMMSS.db.gz` before any mutation. You can also
run it manually:

```powershell
py -m src.cli backup
```

Retention is the last 14 snapshots; older copies are pruned automatically.

## Streamlit dashboard

```powershell
py -m streamlit run src/dashboard.py
```

The header shows the latest score time, latest pipeline run time, evidence
count, and number of filings with real bodies - use those as freshness checks.

## Run tests + lint

```powershell
py -m ruff check .
py -m pytest -q
```

## Telegram (optional)

1. Talk to `@BotFather` on Telegram, create a bot, copy the token.
2. Message your bot once, then get your chat id from
   `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. Put both in `.env`:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Scheduling (Windows Task Scheduler)

Use the wrapper script - it sets the working directory and writes a log under
`data\logs\` so a misconfigured CWD doesn't silently break the daily job.

```powershell
$action  = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\zhaow\serenity-killer-playbook\scripts\run_daily.ps1"'
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
Register-ScheduledTask -TaskName 'SerenityKillerDigest' -Action $action -Trigger $trigger -Force
```

To verify the next run will succeed, run the wrapper once manually and check
the latest log file:

```powershell
& C:\Users\zhaow\serenity-killer-playbook\scripts\run_daily.ps1
Get-Content (Get-ChildItem C:\Users\zhaow\serenity-killer-playbook\data\logs -Filter 'run-*.log' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
```

## What's in the box

- 27 seed tickers across InP / SiC / CPO / SiPh / power / DC / nuclear themes.
- Live yfinance prices + crowd contamination.
- EDGAR per-ticker filings + full-body fetch (CHIPS/DoE keyword scan).
- Form 4 insider transactions with officer role.
- Nitter X scraping for smart-money handles.
- Customer partner-page diff snapshots.
- 11-step scoring engine (steps 0-9 + insider) with status/reason persistence.
- Customer-filing reverse-verification (`supplier_relationships`).
- Kelly-lite sizing (`position_sizing_decisions`) consumed by paper trading.
- Pair-trade watchlist + P&L snapshots.
- Exit plans + drawdown monitor.
- Daily markdown digest + optional Telegram + weekly LLM brief.
- Streamlit dashboard with freshness header and ticker drilldown.
- `pipeline_runs` log + WAL-mode SQLite + gzipped daily backups.
- Pytest coverage: schema, scoring, sizing, parsing, CLI, network adapters, customer extraction, backups.

## What's NOT in the box

- Real broker integration beyond Alpaca paper.
- External feeds for chips.gov / NIST / DoE / EU CHIPS (status tracker exists; fetchers do not).
- Multi-user auth on the dashboard (bind to localhost).
- Aggressive JS-rendered scraping (use Playwright if you need it).
