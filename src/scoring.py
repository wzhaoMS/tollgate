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
_KEY_INSIDER_TERMS = (
    "ceo",
    "cfo",
    "cto",
    "chief executive",
    "chief financial",
    "chief technology",
    "president",
)


def _status_rank(status: str) -> int:
    return {"fail": 0, "unknown": 1, "watch": 2, "small": 3, "pass": 4}.get(status, 1)


def _worst(*statuses: str) -> str:
    return min(statuses, key=_status_rank)


def _best_evidence_grade(cx, ticker: str) -> str | None:
    """Return the strongest relationship/evidence grade for a ticker, or None."""
    rows = cx.execute(
        "SELECT grade FROM evidence_log WHERE ticker = ? AND grade IS NOT NULL",
        (ticker,),
    ).fetchall()
    rel_rows = cx.execute(
        "SELECT evidence_grade AS grade FROM supplier_relationships "
        "WHERE supplier_ticker = ? AND direction = 'customer_to_supplier' "
        "AND evidence_grade IS NOT NULL",
        (ticker,),
    ).fetchall()
    best: str | None = None
    best_rank = 0
    for r in [*rows, *rel_rows]:
        g = (r["grade"] or "")[:1].upper()
        rank = _GRADE_RANK.get(g, 0)
        if rank > best_rank:
            best, best_rank = g, rank
    return best


def _serenity_liquidity_trap(cx, ticker: str) -> str:
    """Step 0 from the original plan: avoid becoming post-tweet exit liquidity.

    fail    => latest Serenity signal is >24h old and price moved >15% since signal
    pass    => signal is fresh (<2h) and has not moved >15%
    watch   => signal exists and price moved >15% but is still fresh, or otherwise ambiguous
    unknown => no signal or no comparable price
    """
    row = cx.execute(
        "SELECT s.*, ((julianday('now') - julianday(s.signaled_at)) * 24.0) AS age_hours "
        "FROM serenity_signals s WHERE s.ticker = ? "
        "ORDER BY s.signaled_at DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if not row or not row["price_at_signal"]:
        return "unknown"
    price = cx.execute(
        "SELECT last_close FROM contamination WHERE ticker = ? AND last_close IS NOT NULL",
        (ticker,),
    ).fetchone()
    if not price or not price["last_close"]:
        return "unknown"
    pct = (float(price["last_close"]) - float(row["price_at_signal"])) / float(row["price_at_signal"]) * 100.0
    age = row["age_hours"]
    if age is not None and age > 24 and pct > 15:
        return "fail"
    if age is not None and age < 2 and pct <= 15:
        return "pass"
    if pct > 15:
        return "watch"
    return "pass"


def _capacity_signal(cx, ticker: str, row: dict[str, Any]) -> str:
    """Step 2: shortage >=30% and expansion timeline >=12 months."""
    model = cx.execute(
        "SELECT gap_pct, expansion_timeline_mo FROM capacity_models "
        "WHERE ticker = ? ORDER BY period DESC, updated_at DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    gap = model["gap_pct"] if model else row.get("capacity_gap_pct")
    exp = model["expansion_timeline_mo"] if model else row.get("expansion_timeline_mo")
    if gap is None or exp is None:
        return "unknown"
    shortage = abs(float(gap))
    return "pass" if shortage >= 30 and int(exp) >= 12 else "fail"


def _substitution_risk(cx, ticker: str) -> str:
    """Step 3: at least two short-term non-substitutable answers must hold."""
    row = cx.execute(
        "SELECT status, short_term_non_substitutable_count FROM substitution_assessments "
        "WHERE ticker = ? ORDER BY assessed_at DESC, id DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if not row:
        return "unknown"
    status = (row["status"] or "unknown").lower()
    if status in {"pass", "watch", "fail"}:
        return status
    count = row["short_term_non_substitutable_count"]
    if count is None:
        return "unknown"
    if int(count) >= 2:
        return "pass"
    if int(count) == 1:
        return "watch"
    return "fail"


def _insider_signal(cx, ticker: str, lookback_days: int = 180) -> str:
    """Net insider purchase/sale signal from Form 4 data.

    Transaction codes: 'P' = open-market purchase, 'S' = open-market sale.
    pass  => net dollar buying by insiders
    fail  => net dollar selling by insiders
    watch => activity present but roughly balanced / non-open-market only
    unknown => no Form 4 rows for this ticker
    """
    rows = cx.execute(
        "SELECT txn_code, dollar_amount, relation FROM insider_txns "
        "WHERE ticker = ? AND txn_date >= date('now', ?)",
        (ticker, f"-{lookback_days} days"),
    ).fetchall()
    if not rows:
        expiry = cx.execute(
            "SELECT 1 FROM insider_option_events WHERE ticker = ? AND status = 'open' "
            "AND date(expiry_date) BETWEEN date('now') AND date('now', '+90 days') LIMIT 1",
            (ticker,),
        ).fetchone()
        if expiry:
            return "watch"
        return "unknown"
    buy = sell = key_buy = key_sell = 0.0
    seen_open_market = False
    seen_key_open_market = False
    for r in rows:
        code = (r["txn_code"] or "").upper()
        amt = r["dollar_amount"] or 0.0
        relation = (r["relation"] or "").lower()
        is_key = any(term in relation for term in _KEY_INSIDER_TERMS)
        if code == "P":
            buy += amt
            seen_open_market = True
            if is_key:
                key_buy += amt
                seen_key_open_market = True
        elif code == "S":
            sell += amt
            seen_open_market = True
            if is_key:
                key_sell += amt
                seen_key_open_market = True
    if not seen_open_market:
        return "watch"
    if seen_key_open_market:
        if key_buy > key_sell:
            return "pass"
        if key_sell > key_buy:
            return "fail"
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
      1. Official ``govt_awards`` rows with >= $10M are a pass.
      2. Company-filing keyword hits / curated text are only a watch lead.
    pass    => official award/backstop found
    watch   => company text says CHIPS/DoE/etc., but no official award yet
    unknown => nothing found (absence of evidence, not evidence of absence)
    """
    official = cx.execute(
        "SELECT 1 FROM govt_awards WHERE ticker = ? "
        "AND award_amount_usd >= 10000000 LIMIT 1",
        (ticker,),
    ).fetchone()
    if official:
        return "pass"

    govt_hit = cx.execute(
        "SELECT 1 FROM filings WHERE ticker = ? "
        "AND keyword_hits LIKE '%govt_backstop%' LIMIT 1",
        (ticker,),
    ).fetchone()
    if govt_hit:
        return "watch"

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
    return "watch" if any(kw in blob for kw in _GOVT_KEYWORDS) else "unknown"


def _float_exit_liquidity(cx, ticker: str) -> str:
    """Step 7 override: can the intended position exit within 3 trading days?"""
    row = cx.execute(
        "SELECT short_interest_pct, days_to_exit FROM float_short_interest WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if not row:
        return "unknown"
    days = row["days_to_exit"]
    short_interest = row["short_interest_pct"]
    if days is not None and float(days) > 5:
        return "fail"
    if short_interest is not None and float(short_interest) > 20:
        return "watch"
    if days is not None and float(days) <= 3:
        return "pass"
    return "watch"


def _catalyst_signal(cx, ticker: str, row: dict[str, Any]) -> str:
    """Step 8: require a falsifiable catalyst within 90 days for a clean pass."""
    near = cx.execute(
        "SELECT 1 FROM catalyst_events WHERE ticker = ? "
        "AND falsifiable = 1 AND status IN ('planned','confirmed') "
        "AND date(event_date) BETWEEN date('now') AND date('now', '+90 days') LIMIT 1",
        (ticker,),
    ).fetchone()
    if near:
        return "pass"
    later = cx.execute(
        "SELECT 1 FROM catalyst_events WHERE ticker = ? "
        "AND falsifiable = 1 AND status IN ('planned','confirmed') "
        "AND date(event_date) BETWEEN date('now') AND date('now', '+365 days') LIMIT 1",
        (ticker,),
    ).fetchone()
    if later:
        return "watch"
    cs = row.get("catalyst_score")
    return "pass" if (cs is not None and cs >= 7) else "fail" if cs is not None else "unknown"


def _ma_floor_signal(cx, ticker: str, row: dict[str, Any]) -> str:
    """Step 5: M&A floor > current market cap x 1.5."""
    estimate = cx.execute(
        "SELECT estimated_floor_usd, current_market_cap_usd FROM ma_floor_estimates "
        "WHERE ticker = ? ORDER BY assessed_at DESC, id DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if estimate and estimate["estimated_floor_usd"] and estimate["current_market_cap_usd"]:
        ratio = float(estimate["estimated_floor_usd"]) / float(estimate["current_market_cap_usd"])
        if ratio > 1.5:
            return "pass"
        if ratio >= 1.0:
            return "watch"
        return "fail"

    mcap = row.get("market_cap_usd")
    rev = row.get("revenue_ttm_usd")
    if mcap and rev and rev > 0:
        ma_floor = max(2 * mcap, 5 * rev)
        return "pass" if ma_floor > (1.5 * mcap) else "watch"
    return "unknown"


def score_row(cx, row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"ticker": row["ticker"]}

    # Step -1 / original Step 0: crowd contamination + Serenity tweet liquidity trap.
    crowd = {
        "low": "pass",
        "medium": "watch",
        "high": "fail",
        "unknown": "unknown",
    }.get((row.get("crowdedness") or "unknown").lower(), "unknown")
    trap = _serenity_liquidity_trap(cx, row["ticker"])
    out["step_minus1"] = _worst(crowd, trap) if trap != "unknown" else crowd

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

    # Step 2: Capacity audit (shortage >=30% AND expansion >=12mo).
    out["step_2"] = _capacity_signal(cx, row["ticker"], row)

    # Step 3: Substitution risk.
    out["step_3"] = _substitution_risk(cx, row["ticker"])

    # Step 4: Government backstop — scan curated text + harvested evidence.
    out["step_4"] = _govt_backstop(cx, row["ticker"], row)

    # Step 5: M&A floor.
    out["step_5"] = _ma_floor_signal(cx, row["ticker"], row)

    # Step 6: Insider activity from harvested Form 4 transactions.
    out["step_6"] = _insider_signal(cx, row["ticker"])

    # Step 7: Liquidity — days-to-exit / short interest override, then ADV fallback.
    exit_liq = _float_exit_liquidity(cx, row["ticker"])
    out["step_7"] = exit_liq if exit_liq != "unknown" else _liquidity(cx, row["ticker"])

    # Step 8: Dated falsifiable catalyst inside 90 days, then curated fallback.
    out["step_8"] = _catalyst_signal(cx, row["ticker"], row)

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


def compute_all() -> list[dict[str, Any]]:
    """Compute current scores without writing to the scores table."""
    db.init()
    results: list[dict[str, Any]] = []
    with db.connect() as cx:
        rows = cx.execute("SELECT * FROM chokepoints").fetchall()
        for r in rows:
            d = _row_to_dict(r)
            score = score_row(cx, d)
            results.append(score)
    return results


def _score_insert(score: dict[str, Any]) -> dict[str, Any]:
    insert = {
        f"step_{k.split('_')[1]}" if k != "step_minus1" else "step_minus1": v
        for k, v in score.items()
        if k.startswith("step_")
    }
    insert["ticker"] = score["ticker"]
    insert["overall"] = score["overall"]
    return insert


def persist_scores(scores: list[dict[str, Any]]) -> int:
    """Persist computed scores and return number of rows inserted."""
    db.init()
    inserted = 0
    with db.connect() as cx:
        for score in scores:
            db.insert_score(cx, _score_insert(score))
            inserted += 1
    return inserted


def score_all(*, persist: bool = True) -> list[dict[str, Any]]:
    """Compute all scores, persisting by default for backwards-compatible CLI use."""
    results = compute_all()
    if persist:
        persist_scores(results)
    return results


def latest_scores() -> list[dict[str, Any]]:
    """Return the latest persisted score row per ticker without writing new rows.

    If the scores table is empty (fresh DB), return a compute-only snapshot so
    report paths can still render without creating score history as a side effect.
    """
    db.init()
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT * FROM scores WHERE id IN (SELECT MAX(id) FROM scores GROUP BY ticker)"
        ).fetchall()
        if rows:
            return [_row_to_dict(r) for r in rows]
    return compute_all()


def main() -> None:
    out = score_all(persist=True)
    for r in out:
        print(f"{r['ticker']:<8} {r['overall']:<6} step1={r['step_1']:<8} step8={r['step_8']:<8} step9={r['step_9']:<8}")


if __name__ == "__main__":
    main()
