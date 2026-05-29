"""Scoring engine v0 — applies the 11-step playbook against a chokepoint row.

This v0 only uses local data (the row + recent filings/evidence). Anything we
cannot determine returns 'unknown' rather than a false positive — Serenity's
biggest mistake is letting weak evidence look like strong evidence.
"""
from __future__ import annotations

from typing import Any

from . import db


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


# Evidence grade ranking (best -> worst) so we can pick the strongest item.
_GRADE_RANK = {"A": 4, "B": 3, "C": 2, "D": 1}


def _best_evidence_grade(cx, ticker: str) -> str | None:
    """Return the strongest evidence grade recorded for a ticker, or None."""
    rows = cx.execute(
        "SELECT grade FROM evidence_log WHERE ticker = ? AND grade IS NOT NULL",
        (ticker,),
    ).fetchall()
    best: str | None = None
    best_rank = 0
    for r in rows:
        g = (r["grade"] or "")[:1].upper()
        rank = _GRADE_RANK.get(g, 0)
        if rank > best_rank:
            best, best_rank = g, rank
    return best


def _insider_signal(cx, ticker: str, lookback_days: int = 180) -> str:
    """Net insider purchase/sale signal from Form 4 data.

    Transaction codes: 'P' = open-market purchase, 'S' = open-market sale.
    pass  => net dollar buying by insiders
    fail  => net dollar selling by insiders
    watch => activity present but roughly balanced / non-open-market only
    unknown => no Form 4 rows for this ticker
    """
    rows = cx.execute(
        "SELECT txn_code, dollar_amount FROM insider_txns "
        "WHERE ticker = ? AND txn_date >= date('now', ?)",
        (ticker, f"-{lookback_days} days"),
    ).fetchall()
    if not rows:
        return "unknown"
    buy = sell = 0.0
    seen_open_market = False
    for r in rows:
        code = (r["txn_code"] or "").upper()
        amt = r["dollar_amount"] or 0.0
        if code == "P":
            buy += amt
            seen_open_market = True
        elif code == "S":
            sell += amt
            seen_open_market = True
    if not seen_open_market:
        return "watch"
    if buy > sell:
        return "pass"
    if sell > buy:
        return "fail"
    return "watch"


def _liquidity(cx, ticker: str) -> str:
    """Average daily dollar volume over the last ~20 trading days.

    pass    => >= $10M/day (can build/exit a position without moving the tape)
    watch   => >= $1M/day  (tradeable but size-constrained)
    fail    => <  $1M/day  (illiquid; execution risk dominates)
    unknown => no price/volume data
    """
    rows = cx.execute(
        "SELECT close, volume FROM prices WHERE ticker = ? "
        "AND close IS NOT NULL AND volume IS NOT NULL ORDER BY date DESC LIMIT 20",
        (ticker,),
    ).fetchall()
    dollar_vols = [r["close"] * r["volume"] for r in rows if r["close"] and r["volume"]]
    if not dollar_vols:
        return "unknown"
    avg = sum(dollar_vols) / len(dollar_vols)
    if avg >= 10_000_000:
        return "pass"
    if avg >= 1_000_000:
        return "watch"
    return "fail"


# Government-backstop keywords (CHIPS Act, DoE, DPA Title III, ITC, etc.).
_GOVT_KEYWORDS = (
    "chips act", "chips and science", "department of energy", "doe grant",
    "federal grant", "federal funding", "loan guarantee", "defense production act",
    "dpa title iii", "title iii", "government award", "government grant",
    "preliminary memorandum of terms", "inflation reduction act",
    "investment tax credit", "section 48d", "subsidy", "matching funds",
    "appropriation", "cofund", "co-fund",
)


def _govt_backstop(cx, ticker: str, row: dict[str, Any]) -> str:
    """Detect a government backstop (downside floor) for a ticker.

    Layered, cheapest-first:
      1. The harvested filings' ``keyword_hits`` already flag the ``govt_backstop``
         bucket whenever CHIPS/DoE/DPA language appears in a filing body.
      2. Otherwise scan the curated row's free-text + any harvested evidence
         excerpts + recent filing bodies for the keyword list.
    pass    => backstop language found
    unknown => nothing found (absence of evidence, not evidence of absence)
    """
    govt_hit = cx.execute(
        "SELECT 1 FROM filings WHERE ticker = ? "
        "AND keyword_hits LIKE '%govt_backstop%' LIMIT 1",
        (ticker,),
    ).fetchone()
    if govt_hit:
        return "pass"

    haystacks = [
        (row.get("next_catalyst") or ""),
        (row.get("notes") or ""),
        (row.get("demand_proxy") or ""),
        (row.get("capacity") or ""),
    ]
    ev = cx.execute(
        "SELECT excerpt FROM evidence_log WHERE ticker = ? AND excerpt IS NOT NULL",
        (ticker,),
    ).fetchall()
    haystacks.extend(r["excerpt"] or "" for r in ev)
    blob = " ".join(haystacks).lower()
    return "pass" if any(kw in blob for kw in _GOVT_KEYWORDS) else "unknown"


def score_row(cx, row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"ticker": row["ticker"]}

    # Step -1: Crowd contamination (uses 'crowdedness' field)
    out["step_minus1"] = {
        "low": "pass",
        "medium": "watch",
        "high": "fail",
        "unknown": "unknown",
    }.get((row.get("crowdedness") or "unknown").lower(), "unknown")

    # Step 0: Adverse selection (capital_structure_flag = redflag is auto-fail)
    flag = (row.get("capital_structure_flag") or "unknown").lower()
    out["step_0"] = "fail" if flag == "redflag" else "pass" if flag in {"clean", "atm"} else "unknown"

    # Step 1: Evidence grade. Prefer the strongest grade actually harvested into
    # evidence_log (from filing enrichment); fall back to the curated column.
    grade = _best_evidence_grade(cx, row["ticker"]) or (row.get("evidence_grade") or "U")[:1]
    out["step_1"] = (
        "pass" if grade == "A"
        else "small" if grade == "B"
        else "watch" if grade == "C"
        else "fail" if grade == "D"
        else "unknown"
    )

    # Step 2: Capacity audit (gap >=30% AND expansion >=12mo)
    gap = row.get("capacity_gap_pct")
    exp = row.get("expansion_timeline_mo")
    if gap is None or exp is None:
        out["step_2"] = "unknown"
    else:
        out["step_2"] = "pass" if (gap <= -30 and exp >= 12) else "fail"

    # Step 3: Substitution risk — needs human review; default unknown
    out["step_3"] = "unknown"

    # Step 4: Government backstop — scan curated text + harvested evidence.
    out["step_4"] = _govt_backstop(cx, row["ticker"], row)

    # Step 5: M&A floor (very coarse: mcap < 5x revenue suggests upside if revenue real)
    mcap = row.get("market_cap_usd")
    rev = row.get("revenue_ttm_usd")
    if mcap and rev and rev > 0:
        out["step_5"] = "pass" if mcap / rev < 5 else "watch"
    else:
        out["step_5"] = "unknown"

    # Step 6: Insider activity from harvested Form 4 transactions.
    out["step_6"] = _insider_signal(cx, row["ticker"])

    # Step 7: Liquidity — average daily dollar volume from the prices table.
    out["step_7"] = _liquidity(cx, row["ticker"])

    # Step 8: Catalyst quality (catalyst_score field, threshold 7)
    cs = row.get("catalyst_score")
    out["step_8"] = "pass" if (cs is not None and cs >= 7) else "fail" if cs is not None else "unknown"

    # Step 9: Time to truth (<=365 days passes)
    ttt = row.get("time_to_truth_days")
    out["step_9"] = "pass" if (ttt is not None and ttt <= 365) else "fail" if ttt is not None else "unknown"

    # Step 10: Capital structure (same field reused)
    out["step_10"] = "pass" if flag == "clean" else "watch" if flag == "atm" else "fail" if flag == "redflag" else "unknown"

    # Overall decision
    hard_fails = [out[k] for k in ("step_minus1", "step_0", "step_1", "step_10") if out[k] == "fail"]
    if hard_fails:
        overall = "Pass"
    elif out["step_1"] == "pass" and out["step_8"] == "pass" and out["step_9"] == "pass":
        # Strong setup. Insiders actively selling, or an illiquid tape we can't
        # build size in, tempers conviction down to Watch.
        overall = "Watch" if out["step_6"] == "fail" or out["step_7"] == "fail" else "Buy"
    elif out["step_6"] == "pass" and out["step_8"] == "pass" and out["step_9"] == "pass":
        # Not A-grade evidence yet, but insiders are buying alongside a live
        # catalyst on a near-term clock — worth a Watch upgrade from Skip.
        overall = "Watch"
    elif out["step_4"] == "pass" and out["step_8"] == "pass":
        # A government backstop (CHIPS/DoE/DPA) caps the downside; with a live
        # catalyst that's worth keeping on the Watch list rather than Skip.
        overall = "Watch"
    elif out["step_1"] in {"small", "watch"} or any(out[k] == "unknown" for k in out if k.startswith("step_")):
        overall = "Watch"
    else:
        overall = "Skip"
    out["overall"] = overall
    return out


def score_all() -> list[dict[str, Any]]:
    db.init()
    results: list[dict[str, Any]] = []
    with db.connect() as cx:
        rows = cx.execute("SELECT * FROM chokepoints").fetchall()
        for r in rows:
            d = _row_to_dict(r)
            score = score_row(cx, d)
            # Persist
            insert = {f"step_{k.split('_')[1]}" if k != "step_minus1" else "step_minus1": v
                      for k, v in score.items() if k.startswith("step_")}
            insert["ticker"] = score["ticker"]
            insert["overall"] = score["overall"]
            db.insert_score(cx, insert)
            results.append(score)
    return results


def main() -> None:
    out = score_all()
    for r in out:
        print(f"{r['ticker']:<8} {r['overall']:<6} step1={r['step_1']:<8} step8={r['step_8']:<8} step9={r['step_9']:<8}")


if __name__ == "__main__":
    main()
