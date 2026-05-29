# Serenity-Killer Initial Plan Implementation Goal

Goal: make the app implement the original 9-step Serenity-Killer checklist and Serenity 2.0 upgrades as evidence-backed, auditable code, not just a coarse dashboard.

## Completion Rules

- Every checklist step must persist evidence or an explicit unknown/failed reason.
- Every production command must be testable offline with mocked or seeded data.
- After every implementation task, run the smallest relevant test slice; after a group of tasks, run `ruff` and the full test suite.
- Do not promote a signal to `Buy` unless the source evidence is stored and traceable.

## Task Checklist

- [x] Foundation schema for missing plan concepts
  - [x] `pipeline_runs`
  - [x] `serenity_signals`
  - [x] `supplier_relationships`
  - [x] `capacity_models`
  - [x] `substitution_assessments`
  - [x] `govt_awards`
  - [x] `float_short_interest`
  - [x] `catalyst_events`
  - [x] `position_sizing_decisions`
  - [x] `theme_exposures`
  - [x] `follower_history`

- [x] Checklist step fidelity
  - [x] Step 0: her-tweet liquidity trap using signal timestamp and post-signal price move
  - [x] Step 1: customer filing reverse-verification relationships
  - [x] Step 2: quarterly physical capacity model
  - [x] Step 3: substitution-risk three-question scoring
  - [x] Step 4: official government award backstop, not just keyword hits
  - [x] Step 5: strategic M&A floor model
  - [x] Step 6: insider role/option-expiry context
  - [x] Step 7: float, short interest, and days-to-exit liquidity
  - [x] Step 8: dated 90-day falsifiable catalyst events
  - [x] Step 9: Kelly-lite sizing plus single-name/theme caps

- [x] Serenity 2.0 upgrades
  - [x] Source-feed status for EDGAR, government, EU/NIST/DoE, scholar/jobs/warrants/slides
  - [x] True-vs-consensus model
  - [x] Serenity follower-count reverse indicator
  - [x] Persistent pair-trade watchlist
  - [x] Pair P&L snapshots and equal-dollar hedge sizing
  - [x] Exit plans with default stop, trim, stale-catalyst, analyst-coverage, and capacity-gap thresholds

- [x] Production hardening
  - [x] Split score computation from score persistence
  - [x] Make digest/paper use latest persisted scores by default
  - [x] Make `all` fail fast when `doctor` fails
  - [x] Persist pipeline run outcomes and error counts
  - [x] Add network-adapter tests with mocked responses
  - [x] Add dashboard freshness indicators and ticker-native drilldowns

## Current Focus

Start with foundation schema and scoring fidelity. Those unlock every later source feed and dashboard improvement.