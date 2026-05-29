# Signal Feed — OSINT source stack

Goal: see what Serenity sees, but 24–72 hours **earlier**.
She reads filings and posts to X. We read the same filings before she does, and never let X be our primary source.

## Source stack (her own toolkit, made explicit)

| Source | Method | Latency |
|---|---|---|
| SEC EDGAR 10-K / 10-Q / 8-K | RSS feed + keyword alerts: "sole source", "single source", "primary supplier", "critical material", "dependent on" | Real-time |
| Federal Register / NIST publications | RSS + email alerts | < 1 day |
| EU CHIPS Act announcements (ECCC) | RSS | < 1 day |
| Customer official websites (partners / suppliers pages) | Visualping or ChangeDetection.io watching the page | 24 hours |
| Wayback Machine | Manual diffing every 1–2 weeks | Variable |
| Google Scholar | Alerts on "indium phosphide", "co-packaged optics", "silicon photonics", "SiC foundry", "ELSFP", "external light source" | Real-time |
| LinkedIn | Alerts for senior scientist / VP moves at target companies and their customers | Real-time |
| SEC 8-K customer warrants | EDGAR full-text search | < 1 day |
| Industry conferences | OFC, GTC, MWC, Hot Chips slide repositories | 1–7 days |
| Capitol Trades | Track government insider trading near critical-infra names | < 1 day |
| Form 4 (insider buys / sells) | EDGAR feed per ticker | Real-time |

## Automation skeleton

A minimal pipeline (Make.com / n8n / Pipedream all work):

```
[RSS source] → [keyword filter] → [Claude / GPT classifier] → [Discord channel + DB row]
```

For each hit, the classifier must answer:
1. Which ticker(s) are referenced?
2. What is the candidate evidence grade (A / B / C / D)?
3. Is this a known story or genuinely new?
4. Suggested next step (verify / add to DB / ignore)?

## Anti-noise rules

- Reject hits that only contain ticker mentions without the trigger keyword.
- Reject hits from press-release wires (BusinessWire / GlobeNewswire) unless the wire is the SEC filing itself.
- Reject hits where the same filing was already classified in the last 30 days.

## Cadence

| Activity | Cadence |
|---|---|
| Review automated alerts | Twice daily (morning + evening) |
| Update database rows for held positions | Weekly minimum |
| Run full Step -1 → Step 11 on a new candidate | Same day as first alert |
| Re-grade evidence on existing positions | Quarterly + on new filings |

## What not to subscribe to

- Generic stock-pump Discords
- Free Substack stockpickers without an audited track record
- Any KOL who recommends positions by ticker without showing the underlying filing
- Reddit WSB DD posts (read for entertainment, not for signal)
