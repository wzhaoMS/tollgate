# Run guide — Daily MVP (Sprints 1+2+3+4)

## One-time setup

```powershell
cd C:\Users\zhaow\serenity-killer-playbook
py -m pip install -r requirements.txt
copy .env.example .env
# Edit .env: set EDGAR_USER_AGENT to your real contact email (required by SEC).
```

## Daily commands

```powershell
# Initialize DB (idempotent; safe to re-run)
py -m src.cli init

# Load seed chokepoint rows + write keyword dictionary
py -m src.cli seed

# Pull live prices via yfinance, compute crowd contamination (Step -1)
py -m src.cli prices

# Pull recent EDGAR filings, keyword-filter
py -m src.cli harvest

# Pull Form 4 insider transactions (Step 6)
py -m src.cli insider

# Pull tweets from smart-money X accounts via Nitter mirrors
py -m src.cli tweets

# Snapshot customer partner pages and flag diffs (Step 1 evidence)
py -m src.cli diffwatch

# LLM-extract structured evidence from filing text (Step 1 grade)
py -m src.cli enrich

# Run the 11-step scoring engine
py -m src.cli score

# Pair-trade candidates from current prices (Sprint 3)
py -m src.cli pairs

# Exit-trigger / drawdown monitor (Sprint 4)
py -m src.cli monitor

# Daily markdown digest (+ optional Telegram)
py -m src.cli digest

# Weekly LLM-written brief
py -m src.cli brief

# Do everything in order
py -m src.cli all
```

## Streamlit dashboard

```powershell
streamlit run src/dashboard.py
```

## Run tests

```powershell
py -m pytest -q
```

## Telegram (optional)

1. Talk to `@BotFather` on Telegram, create a bot, copy the token.
2. Message your bot once, then grab your chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. Put both in `.env`:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Schedule it (Windows Task Scheduler)

```powershell
schtasks /Create /SC DAILY /TN "SerenityKillerDigest" /TR `
  "py -m src.cli all" /ST 08:00 /RU "$env:USERNAME" /F
```

## What's in the box now

- 27 seed tickers across InP / SiC / CPO / SiPh / power / DC / nuclear themes.
- Live yfinance prices (incl. foreign listings via TICKER_OVERRIDES).
- Real-time SEC EDGAR keyword-hit filings + LLM extraction via local Claude bridge.
- Form 4 insider tracking.
- Nitter-based X scraping for 19+ smart-money accounts (Serenity, Leopold, Dylan Patel, AyarLabs, Lightmatter, etc.).
- Customer partner-page diff with browser UA.
- Auto crowd-contamination check (5d / 20d / volume ratio).
- 11-step scoring engine with hard fail rules.
- Pair-trade candidate generator by chokepoint theme.
- Drawdown / exit-trigger monitor.
- Daily markdown digest with top movers + cashtag spikes.
- Weekly LLM brief written by Claude 4.7-xhigh via the local bridge.
- Streamlit dashboard.
- Pytest smoke covers schema, seed, scorer, paper, diff cleaner, pairs.

## What's NOT in the box (planned)

- Real broker integration (Alpaca / IBKR)
- Backtesting harness
- Multi-user / scheduling beyond local Task Scheduler
- Aggressive JS-rendered scraping (use Playwright if you need it)

