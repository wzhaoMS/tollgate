# Run guide — Sprint 1 MVP

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

# Pull recent EDGAR filings, keyword-filter, persist hits
py -m src.cli harvest

# Run the 11-step scoring engine over all chokepoints
py -m src.cli score

# Print the daily digest (also posts to Telegram if configured)
py -m src.cli digest

# Or do everything in one go
py -m src.cli all
```

## Run tests

```powershell
py -m pip install pytest
py -m pytest -q
```

## Telegram (optional)

1. Talk to `@BotFather` on Telegram, create a bot, copy the token.
2. Talk to your bot once (so it can DM you), then grab your chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates`.
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

## What's in / out of scope this sprint

In:
- SQLite schema (chokepoints / filings / evidence / scores)
- SEC EDGAR keyword-filtered harvest (8-K / 10-Q / 10-K)
- 11-step scoring v0 (rule-based; unknown values stay unknown)
- Markdown daily digest, optional Telegram delivery
- Local Copilot bridge client (used by next sprint's LLM enrichment)

Out (next sprints):
- Twitter / X scrapers
- Customer website diff (Visualping)
- LLM-driven evidence grading on raw filing text
- Polygon price/volume for crowd-contamination automation
- Streamlit dashboard
- Pair-trade candidate generator
