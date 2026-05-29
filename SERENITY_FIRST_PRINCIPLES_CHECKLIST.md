# Serenity First-Principles Checklist

Source: distilled from Serenity's own posts + 0xKevin/Ai-yi decomposition.
Purpose: map the **complete** methodology to concrete code/data gaps in this
repo so we can build the missing pieces, not just the obvious ones.

**Independently verified**: 2025-05-29 — 124/124 tests pass, ruff clean, 35 CLI commands registered.

## The one-line first principle

> **Trade the supplier of the obvious trade.**
>
> NVDA is obvious → buy its SiC foundry (XFAB).
> Marvell's CPO is obvious → buy the laser it must use (SIVE).
> Hyperscaler buildout is obvious → buy the transformer (HPS.A).

Everything below exists to make that one sentence systematic, evidence-backed,
and falsifiable — instead of a vibe trade.

---

## Layer 0 — Four underlying economic principles

| # | Principle | Code/data needed | Current status |
|---|---|---|---|
| 0.1 | Pricing power = demand certainty × supply inelasticity | `pricing_power_scores(ticker, demand_certainty, supply_inelasticity, lead_time_months, capex_cycle_years)` | ⚠️ partial via `_capacity_signal` + substitution risk |
| 0.2 | Information edge only exists where coverage is small | analyst coverage count, exchange/region tag, market-cap band filter | ✅ `fundamentals.sell_side_analysts` + `_info_edge_signal` (Buy gate) |
| 0.3 | Customer filing > sell-side research | `supplier_relationships` populated from customer 10-Ks | ✅ schema + extractor + `customer_harvest` CLI |
| 0.4 | M&A floor = strategic value / market cap | `ma_floor_estimates` with potential acquirers + strategic rebuild cost | ✅ `potential_acquirers` + `ma_floor.compute_floor` (50× heuristic) |

---

## Layer 1 — Sector rotation map ("where is money flowing next?")

Serenity's chain: `HBM → optical transceivers → CPO + external lasers → foundry/substrates → ???`

- [x] **`theme_rotation_stages`** table: theme, stage_idx, representative_tickers, last_stage_inflow_proxy.
- [x] **`upstream_links`** table: downstream_theme → upstream_theme (so the dashboard can show "next stop").
- [x] Daily rotation signal: 20d relative-strength of each stage; flag a rotation event when stage N's RS rolls over while stage N+1's RS turns up.
- [ ] Dashboard panel: "money is currently sitting at stage N, next stage is M, tickers in M with low coverage are …".

Status: ✅ `src/rotation.py` (`compute_rotation_signal` + `rotation` CLI). 5 builtin stages (HBM→optical→CPO→foundry→power). Signal states: hot/rolling/cold/unwinding.

---

## Layer 2 — 6-condition chokepoint filter (every Buy must pass)

| Cond | What | Code today | Gap |
|---|---|---|---|
| 2.1 Exclusive / duopoly / de-facto monopoly | step_2/3 in `scoring._capacity_signal` + `_substitution_risk` | ✅ partial | need explicit competitor count + market-share table |
| 2.2 Small market cap (acquirable) | `chokepoints.market_cap_usd` + `_info_edge_signal` | ✅ used in Buy gate | done |
| 2.3 Customer evidence in filings | `supplier_relationships` via `relationships` / `customer_harvest` | ✅ done | need EDGAR throttle recovery to populate live |
| 2.4 Mispriced by cyclical / legacy drag | `fundamentals` + `_mispricing_signal` | ✅ done | data still needs population |
| 2.5 Government backing (CHIPS / DoE / EU CHIPS) | step_4 + `govt_awards` + built-in seed | ✅ 6 CHIPS awards loaded | live feed fetchers still missing |
| 2.6 Re-rate trigger within 90 days | step_8 + `catalyst_events` | ✅ schema + scoring | needs population from earnings calendar + GTC/CES dates |

---

## Layer 3 — OSINT source stack (her real edge)

| Source | Code today | Gap |
|---|---|---|
| Customer official supplier list (page diff) | `src/scrapers/customer_diff.py` | ⚠️ only static seed pages; need per-customer supplier-page URL registry + diff highlighting of *removed* names ("Ayar dropped Macom/LITE") |
| Customer 10-K mentioning supplier | `customer_relationships.extract_from_filings` | ✅ done; **needs run on production DB** |
| NIST / Commerce / DoE official filings | `source_feed_status` tracker | ❌ no fetchers |
| CHIPS Act 1/2 award blueprints | `govt_awards` | ❌ no fetcher; manual seed only |
| Customer warrants / equity stakes (e.g. AMZN → Celestial) | new `customer_warrants` table | ❌ missing |
| Academic papers (CPO packaging, laser yields) | new `research_papers(ticker, paper_url, abstract, relevance)` | ❌ missing |
| Test equipment / yield rumors | new `industry_chatter(source, ticker, claim, confidence)` | ❌ missing |
| Board-change M&A signals ("new directors with M&A experience") | new `governance_events(ticker, event_type, person, prior_ma_exp_bool, source_url)` | ❌ missing |
| Peer/co-vendor announcements (Wiwynn↔Ayar) | new `co_vendor_events(supplier, peer, customer, date, source_url)` | ❌ missing |
| AI-assisted acquisition-chain modeling (Gemini sim) | LLM bridge exists | ⚠️ no `acquisition_chain` table or pipeline |

---

## Layer 4 — Position sizing & leverage

| Concept | Code today | Gap |
|---|---|---|
| Kelly-lite quarter-Kelly | `risk_sizing.kelly_lite_pct` | ✅ done |
| Single-name 5% cap + theme 15% cap | `calculate_position_size` | ✅ done |
| Days-to-exit liquidity cap | `_float_exit_liquidity` + sizing | ✅ done |
| **% of float owned target** (she owns ~1% of SIVE float) | new column on `position_sizing_decisions.float_ownership_target_pct` | ❌ missing |
| Tolerance for 15–25% daily drawdowns | drawdown alerts exist | ⚠️ not connected to sizing decision (should reduce size when 20d vol > X) |
| Long-dated options leverage (EWY 2028 calls) | nothing | ❌ no options sizing module |

---

## Layer 5 — Anti-late-entry / anti-contamination guards

| Guard | Code today | Gap |
|---|---|---|
| Hard pass if >24h after her tweet AND >15% post-tweet move | step 0 `_serenity_liquidity_trap` | ✅ schema + scoring; CSV seeder (`seed_serenity`) ready; needs populated rows |
| Track her follower growth as reverse indicator | `follower_history` + `strategy_signals.reverse_crowd_alerts` + `seed_followers` CSV | ✅ schema + seeder; needs scraper to populate continuously |
| Independent verification gate before Buy | `_independent_verification` requires ≥1 non-Serenity A/B-grade source in last 30d | ✅ done; Buy demotes to Watch when missing |

---

## Layer 6 — M&A floor model (Marvell-buys-Sivers math)

Schema exists in `ma_floor_estimates`; `src/ma_floor.py` now populates it.

- [x] `potential_acquirers(target_ticker, acquirer_name, acquirer_ticker, strategic_value_usd, evidence_url)`.
- [x] Compute `ma_floor_usd = max(2 * current_mcap, strategic_value_usd / 50)` (Serenity's heuristic).
- [x] Step_5 passes only when `ma_floor_usd > 1.5 * current_mcap`.
- [ ] Surface acquirer list in the dashboard ticker drilldown.

---
---

# PART 1 — 9-Step Independent Verify Checklist (code mapping)

> Rule: signal received → don't open position → run all 9 steps → all pass → then build.
> Purpose: use her as **signal source**, not **trade source**.

| Step | Name | Scoring Module | CLI | Data Table | Status | Gap |
|------|------|---------------|-----|------------|--------|-----|
| **⛔ 0** | **Liquidity Trap** — skip if >24h after tweet AND >15% move | `scoring._serenity_liquidity_trap` (step_minus1) | `seed_serenity` | `serenity_signals` | ✅ Logic done | ❌ No live scraper — CSV seed only; need auto-ingest from X/analysissite/schwerelos |
| **1** | **Customer Filing Reverse-Verify** — confirm sole/single source in 10-K | `scoring.score_row` step_1 (`_best_evidence_grade`) | `relationships`, `customer_harvest` | `supplier_relationships`, `evidence_log` | ✅ Logic done | ⚠️ EDGAR throttled — 0 rows populated live |
| **2** | **Physical Capacity Verify** — gap ≥30%, expansion ≥12mo | `scoring._capacity_signal` (step_2) | `score` | `capacity_models` | ✅ Logic done | ❌ No data populated — needs manual or API import of capacity numbers |
| **3** | **Substitution Risk 3-Question** — ≥2 "no substitute" answers | `scoring._substitution_risk` (step_3) | `score` | `substitution_assessments` | ✅ Logic done | ❌ No data populated — needs manual research per ticker |
| **4** | **Government Backstop** — official doc names the company | `scoring._govt_backstop` (step_4) | `seed_govt` | `govt_awards`, `filings` | ✅ Logic + 6 awards loaded | ❌ No live chips.gov/NIST/EU fetcher |
| **5** | **M&A Floor Estimate** — floor > 1.5× market cap | `scoring._ma_floor_signal` (step_5) | `mafloor` | `ma_floor_estimates`, `potential_acquirers` | ✅ Logic + 11 acquirers + 2 floors computed | ⚠️ Only SIVE+XFAB have market_cap populated |
| **6** | **Insider Behavior** — net buy, no large expiring options | `scoring._insider_signal` (step_6) | `insider` | `insider_txns`, `insider_option_events` | ✅ Logic done | ⚠️ Buy gate — demotes to Watch on fail; data needs EDGAR Form 4 harvest |
| **7** | **Float / Short Interest / Liquidity** — exit in ≤3 days | `scoring._liquidity` + `_float_exit_liquidity` (step_7) | `score` | `float_short_interest`, `prices` | ✅ Logic done | ⚠️ Buy gate — demotes to Watch on fail; data needs population |
| **8** | **Re-rate Trigger Timeline** — ≥1 catalyst in 90 days | `scoring._catalyst_signal` (step_8) | `score` | `catalyst_events` | ✅ Logic done | ❌ No data populated — needs earnings calendar + event dates |
| **9** | **Position Sizing (Kelly-Lite)** — quarter-Kelly, 5% cap, 15% theme cap | `risk_sizing.kelly_lite_pct` + `calculate_position_size` | `size` | `position_sizing_decisions` | ✅ Full implementation | ✅ Working — 4 cap layers (raw Kelly, single-name, theme, liquidity) |

### Part 1 Summary
- **Logic complete**: 10/10 steps have scoring code ✅
- **Data populated**: 2/10 (govt_awards, potential_acquirers partially) ⚠️
- **Live feed automation**: 0/10 ❌ — all depend on manual CSV or throttled EDGAR

---

# PART 2 — Six Structural Upgrades: Serenity 2.0 (code mapping)

### 🚀 Upgrade 1 — Signal Feed Lead-Time (beat her by 24-72h)

> Goal: monitor the same OSINT sources she uses, but with automated alerts.

| Signal Source | Status | Module / Table | Gap |
|---|---|---|---|
| SEC EDGAR 10-K/10-Q/8-K RSS + keyword alerts | ⚠️ | `harvest` CLI fetches filings; `fulltext` fetches bodies | ❌ No real-time RSS keyword filter ("sole source", "single source", "primary supplier") |
| NIST / Commerce / Federal Register | ❌ | — | ❌ No fetcher at all |
| EU CHIPS Act / ECCC announcements | ❌ | — | ❌ No fetcher at all |
| Customer website supplier page changes | ⚠️ | `src/scrapers/customer_diff.py` + `diffwatch` CLI | ❌ No per-customer URL registry; no Visualping/ChangeDetection integration |
| Google Scholar alerts (InP, CPO, SiC, ELSFP) | ❌ | — | ❌ No academic paper tracking |
| LinkedIn job posting alerts | ❌ | — | ❌ No fetcher |
| Customer warrants (SEC 8-K) | ❌ | — | ❌ No `customer_warrants` table |
| Conference slides (OFC/GTC/MWC) | ❌ | — | ❌ No fetcher |

**Overall**: ❌ Not implemented. Core gap — this is the #1 structural edge.

### 🚀 Upgrade 2 — Physical Capacity Audit (quantify what she narrates)

> Goal: for each chokepoint, track supply/demand/gap per quarter.

| Component | Status | Module / Table | Gap |
|---|---|---|---|
| `capacity_models` table (supply, demand, gap %) | ✅ Schema | `capacity_models` queried by `scoring._capacity_signal` | ❌ Zero rows populated — needs manual quarterly Excel-style data entry |
| Per-quarter supply/demand/gap tracking | ❌ | — | ❌ No time-series capacity table (schema is point-in-time) |
| "Chokepoint lifecycle" (when gap closes → pricing power collapses) | ❌ | — | ❌ No expiry/lifecycle model |

**Overall**: ⚠️ Schema exists but 0 data. Need a `capacity_quarterly` table + import pipeline.

### 🚀 Upgrade 3 — True vs Consensus 2-Axis Model

> Goal: only buy "fact true + consensus hasn't found it" (upper-left quadrant).

| Component | Status | Module / Table | Gap |
|---|---|---|---|
| `true_vs_consensus(ticker)` function | ✅ **Done** | `strategy_signals.true_vs_consensus` | Returns: hidden_truth / emerging / consensus / unproven / unknown |
| `consensus_metrics` table | ✅ **Done** | `consensus_metrics(ticker, truth_score, consensus_score, analyst_coverage_count, status)` | ❌ Zero rows populated — needs manual or LLM-assisted classification |
| CLI: `consensus` command | ✅ **Done** | `cli.cmd_consensus` | Prints result for a given ticker |

**Overall**: ✅ **Code done**, ❌ data not populated.

### 🚀 Upgrade 4 — Follower Reverse-Indicator (she is now the market)

> Goal: when her follower growth >15%/week AND she signals a small-cap → that cap will mean-revert in 3-6mo.

| Component | Status | Module / Table | Gap |
|---|---|---|---|
| `follower_history` table | ✅ **Done** | `follower_history(handle, observed_at, follower_count)` | ❌ Zero rows — CSV seeder ready (`seed_followers`), no live scraper |
| `follower_growth_pct(handle, lookback_days)` | ✅ **Done** | `strategy_signals.follower_growth_pct` | Calculates % change over period |
| `reverse_crowd_alerts(handle, growth_threshold_pct=15, max_market_cap=3B)` | ✅ **Done** | `strategy_signals.reverse_crowd_alerts` | Returns alerts when growth + small-cap signals align |
| CLI: `reverse` command | ✅ **Done** | `cli.cmd_reverse` | Prints alerts |
| Live follower scraper | ❌ | — | ❌ No automated X follower count fetcher |

**Overall**: ✅ **Code done**, ❌ scraper missing for continuous data.

### 🚀 Upgrade 5 — Pair Trades (hedge beta, extract alpha)

> Goal: Long underperformer / Short outperformer within same chokepoint theme.

| Component | Status | Module / Table | Gap |
|---|---|---|---|
| Theme classifier (6 themes) | ✅ **Done** | `pair_trade._theme_of` | external_light, sic_foundry, inp_substrate, sip, optical_transport, other |
| `candidates()` — picks lowest vs highest 20d perf per theme | ✅ **Done** | `pair_trade.candidates` | Returns long/short pairs with hedge notional |
| `pair_trade_watchlist` table | ✅ **Done** | Persists open pairs | — |
| `pair_trade_snapshots` table | ✅ **Done** | Records P&L history for each pair | — |
| `sync_watchlist()` + `record_snapshots()` | ✅ **Done** | Auto-persists + tracks pairs | — |
| CLI: `pairs` (print), `pairwatch` (persist + snapshot) | ✅ **Done** | `cli.cmd_pairs`, `cli.cmd_pairwatch` | — |

**Overall**: ✅ **Fully implemented.** 50/50 long/short split, per-theme pairing, snapshot P&L tracking.

### 🚀 Upgrade 6 — Exit Discipline (preset rules, no ad-hoc decisions)

> Goal: predefined exit triggers — never decide in the moment.

| Trigger (from research doc) | Status | Code | Gap |
|---|---|---|---|
| +200% → sell 1/3, trailing -25% | ✅ **Done** | `drawdown.evaluate()` → TP-1 alert | — |
| +500% → sell 1/2, trailing -15% | ✅ **Done** | `drawdown.evaluate()` → TP-2 alert | — |
| -40% from cost → hard stop | ✅ **Done** | `drawdown.evaluate()` → STOP alert | — |
| Price drops >15% from high-water → trailing stop | ✅ **Done** | `drawdown.evaluate()` → TRAIL alert | — |
| Analyst coverage 0→3+ → sell 1/3 (consensus forming) | ❌ | — | ❌ Not tracked — need `fundamentals.sell_side_analysts` time-series + trigger |
| Capacity gap -25%→-5% → sell 1/2 (chokepoint fading) | ❌ | — | ❌ Not tracked — need capacity_quarterly time-series + trigger |
| 18mo holding with no new catalyst → reduce 1/2 | ❌ | — | ❌ Not tracked — need position age + catalyst freshness check |
| M&A rumor confirmed → hold for premium | ⚠️ | `exit_plan.ensure_default` creates placeholder | ❌ No M&A-specific hold logic in drawdown |
| CLI: `monitor` (evaluate), `exitplans` (create defaults) | ✅ **Done** | `cli.cmd_monitor`, `cli.cmd_exitplans` | — |

**Overall**: ⚠️ **Core price-based exits done** (4/4 triggers). **Fundamental-change exits missing** (4 triggers: coverage change, capacity close, time decay, M&A hold).

---

# PART 3 — Five Immediately-Actionable Tasks (code mapping)

| # | Task | Status | What Exists | What's Missing |
|---|------|--------|-------------|----------------|
| **1** | **Build Signal Feed** (SEC RSS, Visualping, Scholar alerts) | ❌ | `harvest`/`fulltext` fetch filings in batch; `diffwatch` does static page snapshots | No real-time RSS keyword alerts; no Visualping/ChangeDetection integration; no Scholar alerts; no n8n/Make automation pipeline |
| **2** | **Run 9-Step Checklist on all holdings** | ⚠️ | `score` CLI runs all 11 steps for every chokepoint row → outputs Pass/Watch/Buy/Skip | Data is mostly empty — 0 capacity_models, 0 substitution_assessments, 0 catalyst_events, 0 insider_txns, 0 float_short_interest rows. Running `py -m src.cli score` will produce results but almost everything will be "unknown" |
| **3** | **Build Capacity Audit Table** (InP/SOI/SiC/CW Laser quarterly) | ❌ | `capacity_models` schema exists | Zero rows; no quarterly tracking table; no import pipeline |
| **4** | **Set Follower-Count Reverse Indicator** | ⚠️ | `follower_history` + `reverse_crowd_alerts` + `seed_followers` CSV + `reverse` CLI all exist | No live scraper to auto-fetch follower counts; CSV seeder has no sample data yet |
| **5** | **Open 2 Pair-Trade Observation Positions** (XFAB/WOLF, SIVE/LITE) | ✅ | `pairs` CLI prints candidates; `pairwatch` persists + snapshots; themes cover SiC + external_light | Ready to use — run `py -m src.cli pairwatch` to persist; needs price data from `py -m src.cli prices` first |

---
---

# MASTER GAP SUMMARY (prioritized by impact)

## 🔴 Critical Gaps (no code exists)

| Gap | Impact | Effort |
|-----|--------|--------|
| **Signal feed automation** (RSS + Visualping + Scholar + job alerts) | Core edge — beat her by 24-72h | Large — requires n8n/Make or custom Python daemon |
| **Capacity quarterly time-series** table + import | Determines chokepoint lifecycle / exit timing | Medium — new table + CSV/manual import |
| **EDGAR throttle recovery** → populate supplier_relationships | Filing verification is Step 1 | Low — retry when SEC allows; code exists |

## 🟡 Code Exists, Data Empty

| Gap | Table | Populator |
|-----|-------|-----------|
| Capacity models | `capacity_models` | Manual research per ticker |
| Substitution assessments | `substitution_assessments` | Manual research per ticker |
| Catalyst events | `catalyst_events` | Earnings calendar + conference dates |
| Insider transactions | `insider_txns` | `insider` CLI (EDGAR Form 4) |
| Float/short interest | `float_short_interest` | External data source needed |
| Consensus metrics | `consensus_metrics` | Manual or LLM-assisted classification |
| Follower history | `follower_history` | CSV seed or scraper |
| Serenity signals | `serenity_signals` | CSV seed or scraper |

## 🟢 Fully Working (verified 2025-05-29)

| Module | CLI | Functions verified |
|--------|-----|--------------------|
| `scoring.py` — 11-step engine + 3 buy gates | `score` | `score_row`, `score_all`, `latest_scores` |
| `pair_trade.py` — theme pairing + watchlist | `pairs`, `pairwatch` | `candidates`, `sync_watchlist`, `record_snapshots` |
| `risk_sizing.py` — quarter-Kelly + 4 caps | `size` | `kelly_lite_pct`, `calculate_position_size` |
| `drawdown.py` — 4 exit triggers | `monitor` | `evaluate` (STOP/TP-1/TP-2/TRAIL) |
| `strategy_signals.py` — TvC + reverse crowd | `consensus`, `reverse` | `true_vs_consensus`, `reverse_crowd_alerts` |
| `rotation.py` — 5-stage rotation | `rotation` | `compute_rotation_signal`, 5 builtin stages |
| `supply_chain.py` — obvious→supplier graph | `supplychain` | `upstream_for`, `downstream_for`, 16 builtin links |
| `ma_floor.py` — M&A floor calc | `mafloor` | `compute_floor`, 11 builtin acquirers |
| `seed_signals.py` — CSV importers | `seed_serenity`, `seed_followers`, `seed_govt` | All 3 importers + 6 builtin awards |
| `exit_plan.py` — plan placeholders | `exitplans` | `ensure_for_open_positions` |
| `customer_universe.py` — ticker extractor | `customer_harvest` | `extract_customer_tickers` (6 public customers) |

---

## Operational reminder

She admits she **is now the market** for these small caps (465k followers → her
tweet itself moves price). The repo's posture must be: **either we beat her by
1–6 months via OSINT, or we don't play.** Following her after the tweet = bag
holding. The anti-late-entry guard (Layer 5) is the single highest-priority
piece of code, because it is what stops this whole pipeline from degenerating
into a Twitter-follower simulator.
