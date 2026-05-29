# Chokepoint Database Schema

The database is the system. Every candidate flows through it; no candidate
is acted on outside it.

## Field list (16 columns)

| # | Field | Type | Example | Notes |
|---|---|---|---|---|
| 1 | `Ticker` | string | SIVE | — |
| 2 | `Chokepoint` | string | CW laser array | One bottleneck per row |
| 3 | `End_Customer` | string | Ayar, Wiwynn, MRVL | Comma-separated |
| 4 | `Evidence_Grade` | A/B/C/D | B | From evidence-grading.md |
| 5 | `Evidence_Source_URL` | url | https://sec.gov/… | Hard link to filing |
| 6 | `Capacity` | string | ~50k units/yr | Absolute number when possible |
| 7 | `Demand_Proxy` | string | ~80k units/yr | Best estimate; cite assumption |
| 8 | `Capacity_Gap_Pct` | number | -37.5% | Negative = supply short |
| 9 | `Expansion_Timeline_Mo` | number | 18 | Months until new capacity online |
| 10 | `Substitutes` | string | GaAs, SiP for short reach | Comma-separated |
| 11 | `Market_Cap_USD` | number | 2_100_000_000 | Live |
| 12 | `Revenue_TTM_USD` | number | 50_000_000 | Trailing 12 mo |
| 13 | `EV_Sales` | number | 42.0 | EV ÷ revenue TTM |
| 14 | `Next_Catalyst` | string | Q2 earnings 2026-07 | Date + type |
| 15 | `Catalyst_Score` | number | 7 | From Step 8 in playbook-v2.md |
| 16 | `Crowdedness` | low/med/high | high | Serenity mentions × 1 mo recency |
| 17 | `Capital_Structure_Flag` | clean/atm/dilution/redflag | atm | One word |
| 18 | `Time_to_Truth_Days` | number | 60 | From Step 9 |
| 19 | `Decision` | Buy/Watch/Pass | Watch | Single label |
| 20 | `Last_Updated` | date | 2026-05-28 | YYYY-MM-DD |

> Implementation: a CSV (committed to this repo) for portability, or a Notion
> database for live use. The seed file is `chokepoint-database.csv`.

## How to keep it alive

- Update on the day of any filing, earnings, or material news.
- Re-run Steps -1 through 11 quarterly even for held positions.
- Demote `Decision` immediately if `Evidence_Grade` drops a tier.
- Archive (do not delete) rows that get marked Pass — failure analysis matters.

## Anti-spam rules

- One row per chokepoint, not per news headline.
- Do not add Serenity's daily tweets — only add when there's documentable evidence.
- Do not add D-grade evidence rows at all; they go in a separate `watchlist.csv`.

## Use as decision filter

A trade is permitted only if a row satisfies **all** of:
- `Evidence_Grade ∈ {A, B}`
- `Capacity_Gap_Pct ≤ -30`
- `Expansion_Timeline_Mo ≥ 12`
- `Catalyst_Score ≥ 7`
- `Capital_Structure_Flag ≠ redflag`
- `Time_to_Truth_Days ≤ 365`
- `Crowdedness ≠ high`
- `Decision == Buy`
