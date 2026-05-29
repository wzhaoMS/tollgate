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

## Layer 0 — Four underlying economic principles

| # | Principle | Code/data needed | Current status |
|---|---|---|---|
| 0.1 | Pricing power = demand certainty × supply inelasticity | `pricing_power_scores(ticker, demand_certainty, supply_inelasticity, lead_time_months, capex_cycle_years)` | ❌ missing |
| 0.2 | Information edge only exists where coverage is small | analyst coverage count, exchange/region tag, market-cap band filter | ❌ missing |
| 0.3 | Customer filing > sell-side research | `supplier_relationships` populated from customer 10-Ks | ✅ schema + extractor (`relationships` CLI) |
| 0.4 | M&A floor = strategic value / market cap | `ma_floor_estimates` with potential acquirers + strategic rebuild cost | ✅ schema; ⚠️ no acquirers/rebuild-cost ingestion |

---

## Layer 1 — Sector rotation map ("where is money flowing next?")

Serenity's chain: `HBM → optical transceivers → CPO + external lasers → foundry/substrates → ???`

- [ ] **`theme_rotation_stages`** table: theme, stage_idx, representative_tickers, last_stage_inflow_proxy.
- [ ] **`upstream_links`** table: downstream_theme → upstream_theme (so the dashboard can show "next stop").
- [ ] Dashboard panel: "money is currently sitting at stage N, next stage is M, tickers in M with low coverage are …".
- [ ] Daily rotation signal: 20d relative-strength of each stage; flag a rotation event when stage N's RS rolls over while stage N+1's RS turns up.

Status: ❌ nothing in repo today. Closest is the seed `chokepoints.chokepoint`
free-text column.

---

## Layer 2 — 6-condition chokepoint filter (every Buy must pass)

| Cond | What | Code today | Gap |
|---|---|---|---|
| 2.1 Exclusive / duopoly / de-facto monopoly | step_2/3 in `scoring._capacity_signal` + `_substitution_risk` | ✅ partial | need explicit competitor count + market-share table |
| 2.2 Small market cap (acquirable) | `chokepoints.market_cap_usd` | ✅ data, ❌ not used in scoring | add rule: `mcap < 5B AND mcap > 0.1B = pass` |
| 2.3 Customer evidence in filings | `supplier_relationships` via `relationships` CLI | ✅ done this sprint | needs population (run on real bodies) |
| 2.4 Mispriced by cyclical / legacy drag | P/B, P/E, segment-level revenue | ❌ no fundamentals table | add `fundamentals(ticker, pb, pe, ev_sales, segment_growth_pct)` |
| 2.5 Government backing (CHIPS / DoE / EU CHIPS) | step_4 + `govt_awards` | ✅ schema; ⚠️ no official-source ingestion | build chips.gov / commerce.gov / Federal Register fetchers |
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
| Hard pass if >24h after her tweet AND >15% post-tweet move | step 0 `_serenity_liquidity_trap` | ✅ schema + scoring; ⚠️ needs `serenity_signals` populated (currently empty) |
| Track her follower growth as reverse indicator | `follower_history` + `strategy_signals.reverse_crowd_alerts` | ✅ schema; ⚠️ needs follower scraper |
| Independent verification gate before Buy | nothing | ❌ add: `independent_verifications(ticker, source_url, verified_at)`; require ≥1 row in last 30d before Buy |

---

## Layer 6 — M&A floor model (Marvell-buys-Sivers math)

Schema exists in `ma_floor_estimates`, but no logic populates it. Build:

- [ ] `potential_acquirers(ticker, acquirer_name, acquirer_ticker, strategic_value_usd, evidence_url)`.
- [ ] Compute `ma_floor_usd = max(2 * current_mcap, strategic_value_usd / 50)` (Serenity's heuristic: floor when chokepoint mcap < 50× buyer's strategic value).
- [ ] Step_5 passes only when `ma_floor_usd > 1.5 * current_mcap`.
- [ ] Surface acquirer list in the dashboard ticker drilldown.

---

## Prioritized backlog (smallest-payoff-first → largest)

### Tier A — populate what we already have
- [ ] Run `relationships` on production DB to backfill `supplier_relationships`.
- [ ] Seed `serenity_signals` from her recent tweets (manual CSV import + scraper later) so step 0 becomes live.
- [ ] Manually seed `govt_awards` from the known CHIPS Act 1/2 awards (XFAB, Wolfspeed, GlobalFoundries, Intel, Micron, …).

### Tier B — small new tables, big alpha
- [ ] `fundamentals` (P/B, P/E, segment growth) — enables condition 2.4.
- [ ] `potential_acquirers` + populate M&A floor.
- [ ] Customer **supplier-page registry**: `customer_supplier_pages(customer_ticker, page_url, last_snapshot_id)`; the diff already exists, but we need the *URL list* and we need to flag **removed** names, not just added text.
- [ ] `theme_rotation_stages` + `upstream_links` + relative-strength rotation signal.

### Tier C — new external feeds
- [ ] chips.gov / commerce.gov / Federal Register award fetcher.
- [ ] EU CHIPS / NIST award fetcher.
- [ ] Customer warrant tracker (S-1/S-3/8-K).
- [ ] Board-change extractor from DEF 14A proxies.
- [ ] Academic paper alerts (Scholar) keyed off chokepoint themes.

### Tier D — "trade the supplier of the obvious trade" graph
- [ ] `obvious_trade_supply_chain(obvious_ticker, supplier_ticker, link_strength, evidence_url)`.
- [ ] Dashboard view: pick an obvious-trade ticker (NVDA, MRVL, AVGO, AMZN, …) → see ranked list of small-cap upstream suppliers with chokepoint scores.

### Tier E — Information-edge filter
- [ ] `coverage(ticker, sell_side_analysts, exchange, region, market_cap_band)`.
- [ ] Filter: only score `Buy` when `sell_side_analysts <= 5 AND market_cap_usd < 5B`.

### Tier F — Independent verification gate
- [ ] Before any `Buy` overall: require ≥1 evidence-grade A/B in `evidence_log` *not* sourced from Serenity tweets in the last 30 days.

---

## Operational reminder

She admits she **is now the market** for these small caps (465k followers → her
tweet itself moves price). The repo's posture must be: **either we beat her by
1–6 months via OSINT, or we don't play.** Following her after the tweet = bag
holding. The anti-late-entry guard (Layer 5) is the single highest-priority
piece of code, because it is what stops this whole pipeline from degenerating
into a Twitter-follower simulator.
