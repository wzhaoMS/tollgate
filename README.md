# Serenity-Killer Playbook v2

A personal, structured framework for OSINT-driven supply-chain / bottleneck investing,
inspired by Serenity (@aleabitoreddit) — but engineered to avoid becoming her exit liquidity.

> **Core thesis**: She trades "discovered-but-not-broadcast" facts.
> We trade **the derivative of fact-change** and pre-define exits for when facts fade.

---

## Why this exists

Serenity has a real edge in **information discovery** (customer filings, NIST docs,
CHIPS Act blueprints, customer-website supplier changes, academic capacity papers).
But her process has structural gaps that get exposed in non-bull regimes:

1. No crowd-contamination check — her 465K followers now move illiquid small caps.
2. Evidence levels are blurred ("likely customer" ≈ "sole source" in her writeups).
3. No physical capacity audit — she pitches narrative, not supply/demand math.
4. No capital-structure check — ATM / dilution / customer-concentration are ignored.
5. No exit discipline — long-only, no stops, no take-profit rules.
6. Self-reported (unaudited) 4502% YTD, with only ~10 months of post-AI-supercycle history.

This playbook closes those gaps.

---

## Repository layout

| File | Purpose |
|---|---|
| [`playbook-v2.md`](playbook-v2.md) | The full 11-step checklist (the merged v2) |
| [`evidence-grading.md`](evidence-grading.md) | A/B/C/D evidence framework + examples |
| [`chokepoint-database-schema.md`](chokepoint-database-schema.md) | Database schema (16 fields) |
| [`chokepoint-database.csv`](chokepoint-database.csv) | Seed database (9 tickers) |
| [`signal-feed.md`](signal-feed.md) | OSINT source stack + automation notes |
| [`risk-management.md`](risk-management.md) | Position sizing, pair trades, exit rules |
| [`cognitive-biases.md`](cognitive-biases.md) | Survivorship / reflexivity / adverse-selection guardrails |

---

## How to use

1. Read [`playbook-v2.md`](playbook-v2.md) end-to-end once.
2. Populate [`chokepoint-database.csv`](chokepoint-database.csv) with your own research.
3. For every new candidate, run **all 11 steps** before sizing — no exceptions.
4. Track each position's evidence grade, catalyst quality score, and time-to-truth.
5. Never override the exit rules in [`risk-management.md`](risk-management.md).

---

## Disclaimer

This is a **personal research framework**, not investment advice. Everything here is for
education and decision-hygiene. The author holds no fiduciary duty to the reader.
Small-cap chokepoint stocks routinely drop 25%+ in a single session.
