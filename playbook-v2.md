# Playbook v2 — The 11-Step Checklist

> **Rule**: Receive signal → do not open position → run all 11 steps → all pass → only then size.
> Any single fail = pass on the trade.

---

## Step -1: Crowd Contamination Check (highest priority)

Serenity is now a flow source. Her signals contaminate price before you can act.

| Condition | Action |
|---|---|
| Hours since her tweet > 24 AND price up > 20% | Pass |
| Volume since tweet > 5× 20-day average | Pass |
| Market cap < $3B AND name trending in EN/CN community | Pass — wait for second pullback |
| < 2 hours since tweet AND price flat | Proceed to Step 0 |

Tools:
- `analysissite.vercel.app` (@flamemxy aggregation, timestamped)
- `schwerelos.io` (@stephan_lucka, can compare returns vs price data)

---

## Step 0: Adverse Selection Test

Ask: **"Why is this still undervalued?"**

Acceptable answers (real alpha):
- No coverage / information vacuum
- Too small for institutions to buy
- Foreign small cap with incomplete SEC disclosure
- Niche industry no one understands

Death-sentence answers (drop instantly):
- E. Scandal / SEC investigation / auditor change
- F. Major shareholder distributing
- G. CFO recently resigned / audit firm changed

---

## Step 1: Evidence Grading (A/B/C/D)

| Grade | Evidence | Position Permission |
|---|---|---|
| **A** | Customer filing/annual report explicitly names X as sole / primary / strategic supplier | Core position allowed |
| **B** | Company annual report hints at customer, cross-validated by customer's website / partner page | Small position |
| **C** | Tweet / conference / job postings / patents imply | Observation only |
| **D** | Community speculation / screenshots / AI inference | Do not buy |

Validation steps:
1. Pull target's most recent 10-K / Annual Report from SEC EDGAR or company IR
2. Search for "supplier", "sole source", "single source", "dependent on"
3. Check target's risk factors section
4. Reverse-confirm in the supplier's own filings
5. Use Wayback Machine to look at customer's website partners page history

---

## Step 2: Physical Capacity Audit

Build a supply/demand spreadsheet (template in `chokepoint-database-schema.md`).

```
Capacity Gap % = (Sum of customer demand − X's current capacity) / X's current capacity
```

Pass conditions:
- Capacity Gap > 30%
- Expansion timeline > 12 months (typical: foundry 24–36 mo, wafer 12–18 mo)

---

## Step 3: Substitution Risk

Three questions:

1. Alternative material / process? (e.g., InP can sometimes be replaced by GaAs / SiP)
2. Alternative supplier? (list top-3 competitors with share)
3. Vertical integration risk? (will the hyperscaler / Big Tech build this in-house?)

Pass: at least 2 answers are "no near-term substitute."

---

## Step 4: Government Backstop — quantified

Necessary but not sufficient. CHIPS / NIST listing only means "important", not "profitable."

| Test | Threshold |
|---|---|
| Named in chips.gov, NIST, or EU CHIPS Act 2 official document | Required |
| Funding type | Grant > Loan |
| Funding / capex ratio | > 40% |
| Funding status | Awarded, not "under consideration" |
| Offtake / customer pre-orders for the new capacity | Required |

Pass: at least one official document + awarded funding + > 40% capex coverage + offtake.

---

## Step 5: M&A Floor — quantified

Replace the naive `max(2× MC, revenue × 5)` with:

```
M&A Floor = comparable-transaction EV/Sales × forward revenue × P(deal in 24 mo)

P(deal in 24 mo):
  +0.20  large shareholder > 10% (someone pushing)
  +0.20  company has publicly engaged M&A advisor
  +0.20  new board member with M&A background
  +0.15  customer dependency > 40%
  +0.15  gross margin below industry average (synergy potential)
  +0.10  ≥ 2 comparable transactions in past 24 months
  → capped at 1.00
```

Pass: M&A Floor > current market cap × 1.5.

---

## Step 6: Insider Behavior

- Review Form 4 filings on SEC EDGAR
- CEO / CFO / CTO open-market buys in last 6 months (not stock grants)
- Insider distribution waves = red flag
- Check large unexercised option expiries (vol around those dates)

Pass: net insider buying, no large option overhang within 90 days.

---

## Step 7: Liquidity / Float Trap

- Real float (not total shares outstanding)
- Short interest %: > 20% is double-edged (squeeze possible but institutions may be early)
- `daily dollar volume / planned position size` = days to fully enter/exit
- > 5 days = you cannot exit — pass

Pass: can fully exit position in ≤ 3 trading days.

---

## Step 8: Catalyst Quality Score

Don't just count catalysts — grade them.

| Catalyst type | Score |
|---|---|
| Earnings beat + guidance raise | 10 |
| Customer announces volume order (8-K) | 9 |
| M&A completed or confirmed | 10 |
| Government funding awarded (received) | 7 |
| New analyst coverage + price target | 4 |
| Industry conference (GTC / MWC / OFC) slides | 5 |
| Management TV interview | 2 |
| Social media KOL post | 1 |

Pass: at least one catalyst with score ≥ 7 within the relevant time horizon.

---

## Step 9: Time-to-Truth

```
Time-to-Truth = max(next earnings, next customer milestone, next regulatory event)
```

| TTT | Permission |
|---|---|
| < 90 days | Core position |
| 90–180 days | Small core |
| 180–365 days | Observation |
| > 365 days | Pass, unless valuation extremely cheap |

Rationale: you need a feedback loop to update the thesis.

---

## Step 10: Capital Structure Audit (Serenity skips this — most expensive omission)

Check before sizing:

- ATM / shelf offering active?
- Convertibles outstanding (and at what conversion price)?
- Gross margin trend over last 4 quarters?
- Customer concentration (top customer > 30%?)
- Inventory build relative to revenue trend?
- Capex funding gap (free cash flow − planned capex over next 4 quarters)?

Any single answer that's clearly toxic → pass, no matter how good the supply-chain story.

---

## Step 11: Position Sizing

```
Position % = (P_win × Avg_Gain − P_loss × Avg_Loss) / Avg_Gain × 0.25
                                                              ↑
                                            quarter-Kelly for sanity
```

Hard limits:
- Single ticker ≤ 5% of portfolio
- Same theme / chokepoint basket ≤ 15% combined
- Portfolio cash / macro hedge ≥ 30% (until method is tested in a risk-off cycle)
- Hard stop at −40% from cost basis
- TTT < 90d: up to 5%
- TTT 90–365d: up to 3%
- TTT > 365d: up to 1%

---

## Why all 11 steps matter together

| Failure mode | Step that catches it |
|---|---|
| Buying the top of her tweet | Step -1 |
| Buying a company under SEC investigation | Step 0 |
| Trading on rumor masquerading as fact | Step 1 |
| Bottleneck is narrative, not physical | Step 2, Step 3 |
| Government story will not monetize | Step 4 |
| No M&A floor when story breaks | Step 5 |
| Insiders are exiting while you enter | Step 6 |
| You cannot get out | Step 7 |
| Catalyst is fluff | Step 8 |
| Thesis cannot be falsified for 18 months | Step 9 |
| Company dilutes you to zero | Step 10 |
| One bad position destroys the portfolio | Step 11 |
