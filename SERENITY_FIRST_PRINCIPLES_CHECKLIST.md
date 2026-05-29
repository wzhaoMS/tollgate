# Serenity First-Principles Checklist

Source: distilled from Serenity's own posts + 0xKevin/Ai-yi decomposition.
Purpose: map the **complete** methodology to concrete code/data gaps in this
repo so we can build the missing pieces, not just the obvious ones.

## The one-line first principle

> **Trade the supplier of the obvious trade.**
>
> NVDA is obvious → buy its SiC foundry (XFAB).
> Marvell's CPO is obvious → buy the laser it must use (SIVE).
> Hyperscaler buildout is obvious → buy the transformer (HPS.A).

Everything below exists to make that one sentence systematic, evidence-backed,
and falsifiable — instead of a vibe trade.

---

## ✅ Re-audited mapping — 2026-05-29 (verified, not trusted)

> Re-run independently: `pytest` **124 passed**, `ruff` **clean**, `doctor`
> **0 errors / 0 warnings**, DB **33 tables**. Status below was confirmed by
> reading the actual modules + `PRAGMA table_info` + row counts, **not** by
> trusting prior agent notes.
>
> **Headline finding:** almost every piece of *schema + scoring logic* already
> exists. The real gap is **(a) live data population (most new tables have 0
> rows)** and **(b) external signal-feed fetchers (none exist yet).** Legend:
> ✅ done & working · ⚠️ logic/schema present but unpopulated or partial · ❌ missing.

### Part 1 — The 9-step independent verify checklist (run on any of her tickers)

| # | Step | Where it lives | Status |
|---|---|---|---|
| 0 | Liquidity-trap (>24h after tweet & >15% move ⇒ pass) | `scoring._serenity_liquidity_trap` → `step_minus1`; table `serenity_signals` | ⚠️ logic ✅, `serenity_signals` = **0 rows** (seed via `seed_serenity`) |
| 1 | Customer-filing reverse-verify (sole/single/primary source) | `enrich/customer_relationships` + `supplier_relationships` + `customer_harvest` CLI | ⚠️ code ✅, data blocked by EDGAR 403 throttle |
| 2 | Physical capacity (supply vs demand, gap %, expansion cycle) | `scoring._capacity_signal` (`step_2`) + table `capacity_models` | ⚠️ heuristic ✅; `capacity_models` = **0 rows**, **no populate CLI** |
| 3 | Substitution risk (material / supplier / self-build) | `scoring._substitution_risk` (`step_3`) | ✅ |
| 4 | Government backstop (CHIPS/NIST/EU, funding >$10M) | `scoring._govt_backstop` (`step_4`) + `govt_awards` | ⚠️ logic ✅ + 6 seeded awards; **live feed fetchers ❌** |
| 5 | M&A floor (`max(2×mcap, strat/50) > 1.5×mcap`) | `scoring._ma_floor_signal` (`step_5`) + `ma_floor` CLI | ✅ (11 acquirers, 2 floors computed) |
| 6 | Insider behaviour (Form 4 open-market buys) | `scoring._insider_signal` (`step_6`) | ✅ |
| 7 | Float / short-interest / days-to-exit (≤3 days) | `scoring._float_exit_liquidity` + `_liquidity` (`step_7`) + table `float_short_interest` | ⚠️ logic ✅; `float_short_interest` = **0 rows** (short-% not fed) |
| 8 | Re-rate trigger within 90 days | `scoring._catalyst_signal` (`step_8`) + `catalyst_events` | ⚠️ logic ✅, needs earnings/GTC calendar data |
| 9 | Position sizing (quarter-Kelly, 5% / 15% caps, −40% stop) | `risk_sizing.kelly_lite_pct` + `calculate_position_size` + `size` CLI | ✅ **NOTE:** scoring's `step_9` is *catalyst-timing*, the sizing step lives in `risk_sizing`, not in the 0–10 score row |

### Part 2 — Serenity 2.0 structural upgrades

| # | Upgrade | Where it lives | Status |
|---|---|---|---|
| 1 | Signal lead-time feeds (SEC RSS, NIST/Federal Register, EU CHIPS, Visualping, Scholar, LinkedIn, warrants, vendor slides) | table `source_feed_status` + `sources` CLI; scrapers: `edgar`, `customer_diff`, `insider_form4`, `nitter_x`, `yf_prices` | ❌ **biggest gap** — only status tracker (0 rows); no NIST/FederalReg/EU/Scholar/Visualping/LinkedIn/warrant/slide fetchers |
| 2 | Physical capacity audit (quarterly supply/demand/gap/price-power) | table `capacity_models` (cols: period, supply_units, demand_units, gap_pct, expansion_timeline_mo) | ⚠️ **schema exact-match ✅** but 0 rows + no CLI to enter/compute it |
| 3 | True-vs-Consensus 2-axis model | `strategy_signals.true_vs_consensus` + table `consensus_metrics` + `consensus` CLI | ⚠️ logic ✅, `consensus_metrics` = **0 rows** |
| 4 | Follower-count reverse indicator | `strategy_signals.follower_growth_pct` + `reverse_crowd_alerts` + `follower_history` + `reverse` CLI | ⚠️ logic ✅; `follower_history` = **0 rows**, no scraper to populate daily |
| 5 | Pair trades (Long chokepoint / Short rich peer) | `pair_trade` (`candidates`, `sync_watchlist`, `hedge_notional`) + `pairs` / `pairwatch` CLI | ✅ working |
| 6 | Exit discipline (preset take-profit / trailing / −40% stop) | `exit_plan.ensure_default` + `drawdown.evaluate` + `exitplans` / `monitor` CLI | ✅ working |

### Part 3 — 5 things actionable today

| # | Action | Status / what's needed |
|---|---|---|
| 1 | Build signal feed (RSS + Visualping + Scholar alerts) | ❌ **needs new fetchers** (see Part 2 #1 / Tier C) |
| 2 | Run the 9-step checklist on all her holdings | ✅ `py -m src.cli score` produces step_-1..10; ⚠️ seed her holdings + `serenity_signals` first |
| 3 | Build a capacity-audit table | ⚠️ `capacity_models` exists — needs a `capacity` CLI to populate + feed `step_2` |
| 4 | Follower-count reverse-indicator script | ✅ `reverse` CLI logic exists; ⚠️ needs a daily follower scraper |
| 5 | Open 2 paper pair trades (XFAB/WOLF, SIVE/LITE) | ✅ `pair_trade.candidates` + `pairwatch` already track these |

### Verified missing pieces (do these next)

1. **External signal-feed fetchers** (Part 2 #1 / Part 3 #1) — NIST, Federal Register, EU CHIPS, Google Scholar, Visualping/ChangeDetection, LinkedIn, customer-warrant (8-K), vendor-slide. Only `source_feed_status` tracking exists.
2. **`capacity` CLI + populator** for `capacity_models` (Part 2 #2 / Part 3 #3) — table is ready, no way to fill it, and `_capacity_signal` does not yet read it.
3. **Daily follower scraper** to fill `follower_history` so `reverse` produces live alerts (Part 2 #4 / Part 3 #4).
4. **Short-interest feed** into `float_short_interest` so `step_7` uses real SI% (Part 1 #7).
5. **Data population** of `serenity_signals`, `consensus_metrics`, `catalyst_events` (all 0 rows) — every gate's *logic* is built and tested but starved of inputs.
6. **Dashboard panels** for rotation, supply-chain upstream, M&A-floor acquirer drilldown, capacity audit (none wired into `src/dashboard.py` yet).

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

Status: ✅ `src/rotation.py` (`compute_rotation_signal` + `rotation` CLI).

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

## Prioritized backlog (smallest-payoff-first → largest)

### Tier A — populate what we already have
- [x] `customer_harvest` CLI to scan customers' own 10-Ks for supplier mentions (EDGAR throttle-limited; retry later).
- [x] CSV seeders for `serenity_signals` and `follower_history` (`seed_serenity`, `seed_followers`).
- [x] Built-in CHIPS Act `govt_awards` seed (XFAB, WOLF, GFS, INTC, MU, TSM — loaded live).

### Tier B — small new tables, big alpha
- [x] `fundamentals` (P/B, P/E, EV/Sales, segment growth) + `_mispricing_signal` (condition 2.4).
- [x] `potential_acquirers` + `ma_floor.compute_floor` + Buy gate via step_5.
- [x] `theme_rotation_stages` + `upstream_links` + `compute_rotation_signal` (RS + rotation-to-next flag).
- [ ] Customer **supplier-page registry**: `customer_supplier_pages(customer_ticker, page_url, last_snapshot_id)`; diff must flag *removed* names, not only added text.

### Tier D — "trade the supplier of the obvious trade" graph
- [x] `obvious_trade_supply_chain(obvious_ticker, supplier_ticker, link_strength, evidence_url)` + 16 built-in links.
- [x] CLI: `supplychain --for NVDA` returns ranked upstream suppliers with score + mcap.
- [ ] Dashboard view: pick an obvious-trade ticker → see ranked upstream suppliers.

### Tier E — Information-edge filter
- [x] `_info_edge_signal` uses `fundamentals.sell_side_analysts` + `market_cap_usd`; Buy requires it.

### Tier F — Independent verification gate
- [x] `_independent_verification`: before any `Buy`, require ≥1 non-Serenity A/B-grade evidence row in last 30 days.

### Tier C — new external feeds (still missing)
- [ ] chips.gov / commerce.gov / Federal Register award fetcher.
- [ ] EU CHIPS / NIST award fetcher.
- [ ] Customer warrant tracker (S-1/S-3/8-K).
- [ ] Board-change extractor from DEF 14A proxies.
- [ ] Academic paper alerts (Scholar) keyed off chokepoint themes.
- [ ] Follower-count scraper for `follower_history`.

---

## Operational reminder

She admits she **is now the market** for these small caps (465k followers → her
tweet itself moves price). The repo's posture must be: **either we beat her by
1–6 months via OSINT, or we don't play.** Following her after the tweet = bag
holding. The anti-late-entry guard (Layer 5) is the single highest-priority
piece of code, because it is what stops this whole pipeline from degenerating
into a Twitter-follower simulator.
