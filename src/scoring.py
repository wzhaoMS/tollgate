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

    # Step 1: Evidence grade
    grade = (row.get("evidence_grade") or "U")[:1]
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

    # Step 4: Government backstop — needs filing scan; default unknown
    out["step_4"] = "unknown"

    # Step 5: M&A floor (very coarse: mcap < 5x revenue suggests upside if revenue real)
    mcap = row.get("market_cap_usd")
    rev = row.get("revenue_ttm_usd")
    if mcap and rev and rev > 0:
        out["step_5"] = "pass" if mcap / rev < 5 else "watch"
    else:
        out["step_5"] = "unknown"

    # Step 6: Insider — needs Form 4 scrape; default unknown
    out["step_6"] = "unknown"

    # Step 7: Liquidity — needs market data; default unknown
    out["step_7"] = "unknown"

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
        overall = "Buy"
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
