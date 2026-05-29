# Risk Management

Position sizing, pair structure, exits. This is the file that decides whether
the playbook makes money over a full cycle, not just in a bull run.

## Position sizing — quarter-Kelly with hard caps

```
Position % = (P_win × Avg_Gain − P_loss × Avg_Loss) / Avg_Gain × 0.25
```

Hard caps (override Kelly if smaller):

| Constraint | Limit |
|---|---|
| Single ticker | ≤ 5% of portfolio |
| Same theme / chokepoint basket | ≤ 15% combined |
| Cash / macro hedge | ≥ 30% until method validated in a risk-off cycle |
| Hard stop from cost basis | −40% |

Sizing by Time-to-Truth (Step 9):

| TTT | Max size |
|---|---|
| < 90 days | 5% |
| 90–365 days | 3% |
| > 365 days | 1% |

## Pair trade construction

We use pairs sparingly. The naive "long X / short same-theme peer" can be misleading
when betas differ by 5–10×.

| Hedge goal | Better instrument |
|---|---|
| Hedge small-cap beta | Short Russell 2000 ETF (IWM) |
| Hedge semis theme | Short SOXX / SMH (size-matched) |
| Hedge specific over-extended peer | Short a similar-cap, similarly-valued peer — never short a $27B peer to hedge a $2B name |
| Hedge market drawdown | SPY puts, sized to ~0.5× portfolio delta |

Acceptable pairs (illustrative):
- Long SIVE / Short small-cap photonics ETF if one exists; otherwise no hedge
- Long XFAB / Short a similar SiC name with similar liquidity, not WOLF
- Long AXTI / Short a sized-down basket of optical-component names

## Exit discipline (pre-committed, do not negotiate in the moment)

| Trigger | Action |
|---|---|
| +200% from cost | Sell 1/3, trailing stop −25% on remainder |
| +500% from cost | Sell 1/2, trailing stop −15% on remainder |
| Sell-side coverage goes 0 → ≥ 3 firms | Sell 1/3 (consensus forming, alpha decaying) |
| Capacity gap closes from < −25% to > −5% | Sell 1/2 (bottleneck is dissolving) |
| Confirmed acquisition rumor | Hold for premium |
| −40% from cost | Hard stop — no re-justification allowed |
| Held > 18 months with no new catalyst | Reduce 1/2 (opportunity cost) |
| Evidence Grade drops one tier (A→B or B→C) | Reduce 1/3 immediately |
| Capital structure flag turns to `redflag` | Exit fully |

## Drawdown management at portfolio level

| Portfolio drawdown | Action |
|---|---|
| −5% in a month | Pause new positions; re-rate all open positions |
| −10% in a month | Reduce all small-cap positions by 1/3 |
| −20% from peak | Move to maximum cash, reassess method |

## Position log discipline

For every position, record:
- Entry date / price
- Entry rationale (link to filing(s))
- Evidence grade at entry
- Catalyst horizon (TTT in days)
- Exit triggers (pre-committed, copy from above)
- Outcome (closed P&L, days held)

A position without all of these recorded **before** entry is unauthorized.
