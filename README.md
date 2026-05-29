# Tollgate

**Supply-chain chokepoint intelligence for AI/semiconductor investing.**

Tollgate is a personal, evidence-driven research pipeline for finding the companies
that sit at the *tollgate* of a crowded trade — the upstream suppliers, substrates,
and bottlenecks that every "obvious" AI winner quietly depends on — and scoring them
with discipline so you act on **verified facts**, not narrative or hype.

> **Core idea:** Don't chase the obvious trade. Trade the **supplier of the obvious trade** —
> the chokepoint that collects a toll on the whole build-out — and pre-define your exit
> for when the fact that made it special stops being secret.

This project is *inspired by* the public OSINT methodology of Serenity
([@aleabitoreddit](https://x.com/aleabitoreddit)), but is engineered specifically to
close the structural gaps in that style and to avoid becoming late-cycle exit liquidity.
It is not affiliated with, endorsed by, or representative of any individual.

> ⚠️ **Not investment advice.** This is a personal, educational research project provided
> "as is" with no warranty. See [`DISCLAIMER.md`](DISCLAIMER.md) before using anything here.

---

## Why it exists

The OSINT discovery edge is real — customer filings, NIST designations, CHIPS Act
blueprints, customer-website supplier-page changes, and academic capacity papers all
leak supply-chain truth before the market prices it. But discovery alone is dangerous
in non-bull regimes. Tollgate enforces five disciplines that pure narrative investing skips:

1. **Crowd-contamination check** — a name with 400K+ followers piling in is no longer undiscovered.
2. **Evidence grading (A/B/C/D)** — "likely customer" must never be treated as "sole source."
3. **Physical capacity audit** — supply/demand gap math, not vibes.
4. **Capital-structure screen** — ATM shelves, dilution, and customer concentration are red flags.
5. **Exit discipline** — pre-defined drawdown, gap-close, staleness, and M&A-hold triggers.

The scoring engine returns **`unknown` instead of a false positive** whenever evidence is
missing — because letting weak evidence look strong is the single most expensive mistake.

---

## What's in the box

A working Python pipeline (`src/`) plus a Streamlit dashboard:

- **SQLite store** with idempotent migrations (`src/db.py`).
- **OSINT harvesters** — EDGAR 8-K/10-Q/10-K, Form 4 insider trades, customer
  supplier-page diffs, smart-money X/nitter feeds, EDGAR full-text + Federal Register scans.
- **11-step scoring engine** (`src/scoring.py`) — crowd/liquidity trap, evidence grade,
  capacity gap, substitution risk, government backstop, M&A floor, insider flow, exit
  liquidity, dated catalyst, time-to-truth, and capital structure. Plus information-edge,
  mispricing, and independent-verification gates before any "Buy."
- **Capacity lifecycle tracker** — flags chokepoints whose supply/demand gap is *closing*
  (a possible exit-liquidity zone) vs. still widening.
- **Rotation + supply-chain mapping** — stage-by-stage theme rotation and customer→supplier graphs.
- **Signal feeds + governance/M&A tracking** — automated sole-source and CHIPS/DoE alerting.
- **Risk + paper trading** — Kelly-lite sizing, pair-trade watchlists, exit plans, drawdown
  monitor, and optional Alpaca paper sync.

---

## Quick start

```powershell
# Python 3.11+ (invoked as `py` on Windows)
py -m pip install -e ".[dev]"

# 1. Create the schema
py -m src.cli init

# 2. Seed the curated chokepoint database + keyword dictionary
py -m src.cli seed

# 3. Load all built-in evidence (capacity, substitution, catalysts, consensus, etc.)
py -m src.cli seed_all

# 4. Score everything against the 11-step playbook
py -m src.cli score

# 5. Launch the dashboard
py -m streamlit run src\dashboard.py
```

Run `py -m src.cli` with no arguments to see every command, and `py -m src.cli doctor`
to validate your environment first.

---

## Key CLI commands

| Command | What it does |
|---|---|
| `init` / `seed` / `seed_all` | Create schema, load curated DB, seed all built-in evidence tables |
| `score` | Run the 11-step scoring engine over every chokepoint |
| `candidates` | Seed the sub-$10B screen candidates and print their evidence-based score breakdown |
| `harvest` / `fulltext` / `enrich` | Pull + keyword-filter EDGAR filings and extract A/B/C/D evidence |
| `prices` / `insider` / `tweets` / `diffwatch` | Refresh prices/crowding, Form 4s, smart-money tweets, customer-page diffs |
| `capacity` / `lifecycle` | Quarterly supply/demand gaps and chokepoint exit-signal lifecycle |
| `rotation` / `supplychain` | Theme rotation heat and customer→supplier graph |
| `signals` / `alerts` | Scan EDGAR/Federal Register/customer pages and surface unacknowledged alerts |
| `consensus` / `reverse` | True-vs-consensus state and follower/crowd reverse alerts |
| `monitor` / `exitplans` / `size` / `pairs` | Drawdown triggers, exit plans, Kelly-lite sizing, pair-trade candidates |
| `digest` / `brief` / `backtest` | Daily digest, weekly LLM brief, crowd-contamination backtest |
| `all` | Run the full daily pipeline |

---

## Repository layout

| Path | Purpose |
|---|---|
| `src/` | Pipeline: DB, scrapers, scoring, risk, dashboard |
| `tests/` | Pytest suite (run with `py -m pytest`) |
| [`playbook-v2.md`](playbook-v2.md) | The full 11-step checklist |
| [`evidence-grading.md`](evidence-grading.md) | A/B/C/D evidence framework + examples |
| [`chokepoint-database-schema.md`](chokepoint-database-schema.md) | Database schema reference |
| [`signal-feed.md`](signal-feed.md) | OSINT source stack + automation notes |
| [`risk-management.md`](risk-management.md) | Position sizing, pair trades, exit rules |
| [`cognitive-biases.md`](cognitive-biases.md) | Survivorship / reflexivity / adverse-selection guardrails |
| [`RUN.md`](RUN.md) | Operational run notes |

---

## Development

```powershell
py -m pytest        # run the test suite
py -m ruff check .  # lint
```

---

## How to use it well

1. Read [`playbook-v2.md`](playbook-v2.md) once, end to end.
2. Add every new candidate to the chokepoint database with an honest evidence grade.
3. Run **all 11 steps** before sizing — no exceptions. Treat `unknown` as "not verified," not "fine."
4. Track each position's evidence grade, catalyst quality, and time-to-truth.
5. Never override the exit rules in [`risk-management.md`](risk-management.md).
6. Remember: a tweet from a large account is a **signal source**, not a trade source.
   Verify independently before you risk being someone else's exit liquidity.

---

## Disclaimer

This is a **personal research framework, not investment advice.** Everything here is for
education and decision hygiene. The author holds no fiduciary duty to the reader and makes
no representation about any third party. Small-cap chokepoint stocks routinely fall 25%+ in
a single session. Do your own research; trade your own risk.

**Full terms, no-warranty, and limitation of liability: see [`DISCLAIMER.md`](DISCLAIMER.md).**
