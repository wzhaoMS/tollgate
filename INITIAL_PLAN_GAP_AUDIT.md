# Initial Plan Gap Audit

Date: 2026-05-29
Scope: Compare the pasted initial Serenity-Killer strategy plan against the current codebase and live SQLite state.

## Bottom Line

The codebase implements a useful research MVP, but it does not yet implement the original plan as written.

Current code is strongest at:

- EDGAR per-ticker filing harvest.
- Full 10-K/8-K body fetch and keyword scan.
- Form 4 insider transaction harvest.
- Basic price/volume crowd-contamination metrics.
- Coarse 11-step scoring table.
- Basic same-theme pair-trade candidate generation.
- Basic drawdown/take-profit alerting.

The biggest gaps against the original plan are:

1. No Serenity-tweet timestamp based liquidity trap check.
2. No customer-filing reverse verification graph: customer Y says supplier X is sole/critical.
3. No automated physical capacity supply/demand model.
4. Substitution risk is not implemented.
5. Government backstop is too loose: keyword hit, not official funding amount > $10M.
6. M&A floor is only a rough valuation proxy, not the plan's strategic floor model.
7. Float, short interest, and exit-days liquidity are missing.
8. Kelly-lite position sizing and theme exposure caps are missing.
9. True-vs-consensus model is missing.
10. Follower-count reverse indicator is missing.
11. Source-feed stack is partial: EDGAR yes, customer page diff partial, government/EU/NIST/scholar/jobs/warrants/slides mostly no.

Live DB evidence also shows the gap: `evidence_log` is currently `0`, so the most important step, independent evidence grading, is not yet feeding the production score.

## Code/Data Coverage Snapshot

Live tables currently exist only for:

- `chokepoints`
- `filings`
- `evidence_log`
- `scores`
- `prices`
- `contamination`
- `insider_txns`
- `tweets`
- `page_snapshots`
- `positions`

Tables that the initial plan implies but the code does not have:

- `serenity_signals` or `tweet_events`: exact Serenity tweet timestamp, ticker, pre/post price, follower count.
- `supplier_relationships`: supplier X, customer Y, source filing, evidence grade, phrase, direction, confidence.
- `customer_filings`: customer-side filings separate from supplier-side filings.
- `capacity_models`: quarterly supply, demand, gap %, expansion date, assumptions.
- `substitution_assessments`: substitute materials, substitute suppliers, customer self-build risk.
- `govt_awards`: official source, agency, program, award amount, date, URL.
- `float_short_interest`: float, short interest %, borrow/short data, days-to-exit.
- `catalyst_events`: 90-day and 12-month catalysts with dates and falsifiability.
- `position_sizing_decisions`: Kelly inputs, max single-name cap, theme cap, final size.
- `theme_exposures`: aggregate exposure per chokepoint/theme.
- `follower_history`: Serenity follower count over time.
- `pipeline_runs`: run status, data freshness, error counts, git SHA.

## Part 1: 9-Step Checklist Coverage

| Original checklist step | Current code coverage | Gap severity | Evidence | What must change |
|---|---:|---:|---|---|
| Step 0: Liquidity Trap after her tweet | Partial, but concept mismatch | High | `src/scrapers/yf_prices.py:57` computes 5d/20d price and volume contamination; `src/scoring.py:147` maps `crowdedness` to `step_minus1`. | Add `serenity_signals` with exact tweet timestamp and price-at-signal. Implement rule: if signal age >24h and post-signal move >15%, auto-pass/skip. Integrate `analysissite.vercel.app` or `schwerelos.io`, or ingest Serenity tweets directly with timestamps. |
| Step 1: Customer Filing reverse verification | Weak partial | Critical | `src/scrapers/edgar.py:101` fetches company filings for tracked ticker X, not necessarily customer Y; `src/enrich/filing_text.py` exists but live `evidence_log = 0`; `src/scrapers/customer_diff.py:18` watches static partner pages only. | Model customer/supplier pairs. Fetch customer Y's 10-K/annual report, search supplier terms, require explicit source phrase naming X or critical dependency. Persist relationship evidence with direction: customer filing -> supplier. Add Wayback/history support for partner pages. |
| Step 2: Physical Capacity verification | Partial, mostly manual | High | `chokepoints` has `capacity`, `demand_proxy`, `capacity_gap_pct`, `expansion_timeline_mo`; `src/scoring.py:169` checks gap and expansion fields. | Build a capacity time-series model: year/quarter, supply, demand by customer, gap %, expansion timeline, source URLs. Normalize sign convention: original plan says gap >30%; current code passes when `capacity_gap_pct <= -30`. |
| Step 3: Substitution Risk | Missing | Critical | `src/scoring.py:177` explicitly sets `step_3 = unknown`. `chokepoints.substitutes` exists but is not scored. | Implement three-question framework: substitute material/process, substitute suppliers/top-3 share, customer self-build motive. Require at least two short-term-no answers to pass. |
| Step 4: Government Backstop | Partial and currently too permissive | High | `src/scoring.py:109` passes on `filings.keyword_hits LIKE '%govt_backstop%'`; `src/enrich/filing_full.py:117` fetches bodies; live DB has 34 govt-flagged filings. | Replace keyword-only pass with official-source evidence: chips.gov, Commerce, NIST, DoE, EU CHIPS/ECCC. Add award amount and require direct official naming plus funding >$10M for pass. Keep keyword hits as candidate leads, not final pass. |
| Step 5: M&A Floor | Weak partial | High | `src/scoring.py:183` uses `mcap / revenue < 5` as a rough pass/watch. | Implement the plan's floor: potential acquirers, strategic rebuild cost/time, `max(2x current MC, 5x revenue)` and require floor > current MC x 1.5. Add advisor/director/M&A signal extraction. |
| Step 6: Insider Behavior | Good partial | Medium | `src/scrapers/insider_form4.py:194` harvests Form 4; `src/scoring.py:38` scores net open-market P vs S over 180 days. | Filter executive roles: CEO/CFO/CTO/director. Distinguish planned sales vs discretionary sales where possible. Add option-expiration/vesting calendar and insider ownership context. |
| Step 7: Float / Short Interest / Exit-days liquidity | Partial | High | `src/scoring.py:74` uses average daily dollar volume thresholds. No float or short-interest table exists. | Add float, short interest %, borrow/availability if possible, and intended position size. Score days-to-exit: position value / average dollar volume <= 3 trading days. |
| Step 8: Re-rate Trigger within 90 days | Weak partial | Medium | `src/scoring.py:197` uses curated `catalyst_score >= 7`; `src/scoring.py:201` uses `time_to_truth_days <= 365`. | Add dated catalyst table. Require at least one falsifiable catalyst inside 90 days for Buy eligibility. Track 12-month probable catalysts separately. |
| Step 9: Position Sizing | Mostly missing | Critical | `src/alpaca_paper.py:57` syncs 1 share for Buy names; comment says sizing is not wired in. `src/drawdown.py:12` evaluates drawdown alerts only after positions exist. | Implement Kelly-lite sizing, 5% single-name cap, 15% theme cap, correlation/theme exposure limits, and pre-trade sizing decisions. Make drawdown rules part of position creation, not only alerts after the fact. |

## Part 2: Serenity 2.0 Upgrade Coverage

| Upgrade | Current code coverage | Gap severity | Evidence | Required implementation |
|---|---:|---:|---|---|
| Upgrade 1: Source feed before her | Partial | High | EDGAR is implemented in `src/scrapers/edgar.py:162`; customer page snapshots in `src/scrapers/customer_diff.py:18`; Nitter/X scraping in `src/scrapers/nitter_x.py:99`; Telegram digest exists. | Add dedicated feeds for chips.gov, Federal Register, NIST, Commerce, DoE, EU CHIPS/ECCC, Google Scholar, jobs, warrants, and conference/vendor slides. Persist feed freshness/status by source. |
| Upgrade 2: Physical Capacity Audit | Partial | High | Capacity fields exist in schema and scoring, but no model table or extraction. | Add quarterly supply/demand model with assumptions and source links. Dashboard should show capacity gap over time and projected gap closure date. |
| Upgrade 3: True vs Consensus dual-axis model | Missing | Critical | No consensus/coverage/market-discovery fields or tables exist. | Add `truth_score`, `consensus_score`, analyst coverage count, media/social mentions, and institutional discovery indicators. Buy only when fact is strong and consensus is still low. |
| Upgrade 4: Use her as reverse indicator | Missing | Critical | `tweets` table stores cashtags from smart-money handles, but no Serenity follower count or post-tweet price reaction model. | Add follower history, Serenity tweet event table, post-signal return windows, and reverse/short alert logic when follower growth and small-cap squeeze conditions hit. |
| Upgrade 5: Pair trade | Partial | Medium | `src/pair_trade.py:30` generates long lower-20d / short higher-20d same-theme pairs. | Add explicit pair watchlist, beta/volatility sizing, borrow constraints, pair P&L tracking, stop rules, and the specific pairs from the plan (XFAB/WOLF, SIVE/LITE) as monitored paper pairs. |
| Upgrade 6: Exit discipline | Partial | High | `src/drawdown.py:12` handles -40%, +200%, +500%, and trailing-stop alerts. | Add sell/trim execution workflow, analyst coverage trigger, capacity-gap-closing trigger, 18-month no-catalyst trigger, and persisted exit plan per position. |

## Part 3: "Today Can Do" Items Coverage

| Initial action item | Current code coverage | Status | Gap |
|---|---:|---:|---|
| Build Signal Feed | EDGAR yes, customer pages partial, X/Nitter partial | Partial | Missing government/EU/NIST/Federal Register, scholar, jobs, warrants, vendor slides, and source health dashboard. |
| Run all current Serenity holdings through checklist | `scores` table exists with steps | Partial | Checklist is not the original 0-9 and several steps are unknown/coarse. No evidence trace per checklist decision. |
| Build Capacity Audit table | Seed fields only | Missing | No quarterly supply/demand model or assumptions table. |
| Follower-count reverse indicator | None | Missing | No follower history, no weekly/monthly follower growth, no short/reversal alerts. |
| Paper pair trades | Pair candidates only | Partial | No persistent pair portfolio, no pair P&L, no hedge sizing, no watch positions for XFAB/WOLF or SIVE/LITE. |

## Most Important Code Gaps By First-Principles Impact

### 1. The system is not yet trading "fact-change derivative"

The plan's first principle is to trade the derivative of fact-change, not the fact after it is broadcast. Current code primarily scores static rows plus recently harvested filings. It does not yet model:

- when the fact first appeared,
- when Serenity broadcast it,
- when price reacted,
- when consensus discovered it,
- whether the bottleneck is strengthening or fading.

Build order:

1. Add `signal_events` for first-seen source facts.
2. Add `serenity_signals` for broadcast timestamps.
3. Add `market_reaction_windows` for price/volume response after both events.
4. Add `consensus_metrics` for analyst/social/media discovery.

### 2. Evidence grading exists as a concept but not as live data

The schema has `evidence_log`, and scoring reads it, but live DB count is `0`. That means step_1 is mostly curated/manual today.

Build order:

1. Unify filing text fetchers around the fixed `filing_full` resolver.
2. Add customer-side filing ingestion using `chokepoints.end_customer`.
3. Extract and persist supplier relationships into `evidence_log` or a stronger `supplier_relationships` table.
4. Require source URL and exact excerpt for any A/B grade.

### 3. The capacity model is not a model yet

The current `capacity_gap_pct` and `expansion_timeline_mo` fields are useful, but they are single curated values. The plan requires a time-series supply/demand model.

Build order:

1. Add `capacity_models(ticker, period, supply_units, demand_units, gap_pct, source_url, assumptions)`.
2. Add `capacity_events` for capex, new fab/line, yield changes, and customer ramp.
3. Score step_2 from the model, not the seed row.
4. Add an exit trigger when gap closes from shortage to near-balanced.

### 4. Risk management is alerting, not sizing

Drawdown alerts are useful, but the plan says position sizing is the most important step. The code does not calculate a portfolio allocation before opening positions.

Build order:

1. Add `risk_sizing.py` implementing Kelly-lite.
2. Add single-name cap, theme cap, and liquidity/day-to-exit cap.
3. Add `position_sizing_decisions` table.
4. Make `paper` and `alpaca_paper` consume sizing decisions instead of opening 1 share.

### 5. Government backstop should become official-award evidence, not keyword evidence

Current step_4 passes on keyword hits in company filings. The original plan requires official government documents and actual funding >$10M.

Build order:

1. Add `govt_awards` table with agency, program, amount, source URL, official document date.
2. Add chips.gov/Commerce/DoE/NIST/EU feed ingestion.
3. Make `govt_backstop` pass only if official source directly names the company and amount >= $10M.
4. Keep company-filing keyword hits as leads or watch signals.

## Recommended Implementation Roadmap

### Sprint 1: Make the checklist faithful

1. Add missing schema: `signal_events`, `serenity_signals`, `supplier_relationships`, `capacity_models`, `govt_awards`, `float_short_interest`, `catalyst_events`, `position_sizing_decisions`, `pipeline_runs`.
2. Refactor `score_row` so each step returns `{status, reason, evidence_url, evidence_excerpt, confidence}` instead of only a string.
3. Preserve current string columns for dashboard compatibility, but add a JSON detail column or `score_step_details` table.

### Sprint 2: Build the two hardest validators

1. Customer-filing reverse verification: customer Y filing must name supplier X or state dependency.
2. Capacity audit: quarterly supply/demand/gap model and gap-closing exit trigger.

### Sprint 3: Build anti-exit-liquidity logic

1. Serenity tweet timestamp ingestion.
2. Post-tweet price reaction windows.
3. Follower growth history.
4. Direct implementation of Step 0: if >24h after her tweet and >15% move, hard pass.

### Sprint 4: Portfolio/risk layer

1. Kelly-lite sizing.
2. Single-name/theme caps.
3. Days-to-exit liquidity sizing.
4. Pair-trade paper portfolio and P&L.
5. Exit-plan persistence.

### Sprint 5: Source-feed expansion

1. chips.gov, Commerce, DoE, NIST, EU CHIPS/ECCC.
2. Google Scholar alerts or a manual ingestion bridge.
3. Job postings.
4. Vendor slides/conference uploads.
5. Warrants/customer financing disclosures.

## Current Production Meaning

The app is currently good at answering:

- Which tracked chokepoint tickers have recent EDGAR filings?
- Which filings contain relevant keyword buckets?
- Which tickers have Form 4 insider buying/selling?
- Which names look crowded based on recent price/volume?
- Which names pass a coarse, conservative scorecard?
- Which same-theme pairs are extended versus lagging?
- Which open paper positions triggered simple drawdown/take-profit alerts?

The app is not yet good at answering the plan's highest-alpha questions:

- Did Serenity already broadcast this and did price already move too far?
- Did the customer filing independently prove the supplier relationship?
- Is the bottleneck physically scarce by quarter, and when does scarcity end?
- Is the fact true but still undiscovered by consensus?
- Is there an official government award above $10M?
- How large should the position be under Kelly-lite and portfolio caps?
- Should the Serenity crowd itself be a short/reversion signal?

## Final Rating Against Initial Plan

- Checklist automation: 40% implemented.
- Source-feed stack: 35% implemented.
- Evidence discipline: 25% implemented in live data, despite schema support.
- Capacity audit: 20% implemented.
- True-vs-consensus alpha model: 0% implemented.
- Reverse-crowd/follower indicator: 0% implemented.
- Pair trade engine: 45% implemented.
- Exit discipline: 35% implemented.
- Position sizing: 10% implemented.

Overall: the codebase is a strong foundation, but it currently implements the scaffolding of the strategy more than the original strategy itself. The next production push should focus less on more dashboards and more on making each checklist step produce evidence-backed, auditable pass/fail decisions.