"""Kelly-lite position sizing for the original 9-step checklist.

Formula from the plan:

    Position % = (P_win * Avg_Gain - P_loss * Avg_Loss) / Avg_Gain * 0.25

Inputs use probabilities as 0..1 (or 0..100, normalized defensively) and gains/losses
as positive percentages. Output is capped by single-name limit, theme limit, and
exit-liquidity constraints.
"""
from __future__ import annotations

import json
from typing import Any

from . import db


def _prob(value: float) -> float:
    value = float(value)
    if value > 1:
        value /= 100.0
    return min(max(value, 0.0), 1.0)


def _positive_pct(value: float) -> float:
    return abs(float(value))


def kelly_lite_pct(
    *,
    p_win: float,
    avg_gain_pct: float,
    avg_loss_pct: float,
    p_loss: float | None = None,
) -> float:
    """Return quarter-Kelly position size as portfolio percent before caps."""
    win_prob = _prob(p_win)
    loss_prob = _prob(1.0 - win_prob if p_loss is None else p_loss)
    gain = _positive_pct(avg_gain_pct)
    loss = _positive_pct(avg_loss_pct)
    if gain <= 0:
        return 0.0
    edge_fraction = (win_prob * gain - loss_prob * loss) / gain
    return max(0.0, edge_fraction * 0.25 * 100.0)


def calculate_position_size(
    *,
    ticker: str,
    account_value_usd: float,
    p_win: float,
    avg_gain_pct: float,
    avg_loss_pct: float,
    p_loss: float | None = None,
    current_theme_exposure_pct: float = 0.0,
    max_single_name_pct: float = 5.0,
    max_theme_pct: float = 15.0,
    days_to_exit: float | None = None,
) -> dict[str, Any]:
    """Calculate capped position size and return an auditable decision dict."""
    raw_pct = kelly_lite_pct(
        p_win=p_win,
        p_loss=p_loss,
        avg_gain_pct=avg_gain_pct,
        avg_loss_pct=avg_loss_pct,
    )
    theme_remaining = max(0.0, float(max_theme_pct) - float(current_theme_exposure_pct))
    caps = [raw_pct, float(max_single_name_pct), theme_remaining]
    constraints: dict[str, Any] = {
        "raw_quarter_kelly_pct": raw_pct,
        "max_single_name_pct": float(max_single_name_pct),
        "max_theme_pct": float(max_theme_pct),
        "current_theme_exposure_pct": float(current_theme_exposure_pct),
        "theme_remaining_pct": theme_remaining,
    }
    if days_to_exit is not None:
        constraints["days_to_exit"] = float(days_to_exit)
        if float(days_to_exit) > 5:
            caps.append(0.0)
            constraints["liquidity_cap"] = "zero: exit would take more than 5 trading days"
        elif float(days_to_exit) > 3:
            caps.append(min(float(max_single_name_pct), 1.0))
            constraints["liquidity_cap"] = "reduced: exit would take more than 3 trading days"

    capped_pct = max(0.0, min(caps))
    decision = "skip" if capped_pct <= 0 else "size"
    return {
        "ticker": ticker.upper(),
        "p_win": _prob(p_win),
        "p_loss": _prob(1.0 - _prob(p_win) if p_loss is None else p_loss),
        "avg_gain_pct": _positive_pct(avg_gain_pct),
        "avg_loss_pct": _positive_pct(avg_loss_pct),
        "kelly_fraction": raw_pct / 25.0 if raw_pct else 0.0,
        "quarter_kelly_pct": raw_pct,
        "capped_position_pct": capped_pct,
        "dollar_amount": float(account_value_usd) * capped_pct / 100.0,
        "constraints": constraints,
        "decision": decision,
    }


def record_decision(decision: dict[str, Any]) -> int:
    """Persist a sizing decision and return its row id."""
    db.init()
    with db.connect() as cx:
        cur = cx.execute(
            "INSERT INTO position_sizing_decisions "
            "(ticker, p_win, avg_gain_pct, p_loss, avg_loss_pct, kelly_fraction, "
            " quarter_kelly_pct, capped_position_pct, dollar_amount, constraints_json, decision) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                decision["ticker"],
                decision["p_win"],
                decision["avg_gain_pct"],
                decision["p_loss"],
                decision["avg_loss_pct"],
                decision["kelly_fraction"],
                decision["quarter_kelly_pct"],
                decision["capped_position_pct"],
                decision["dollar_amount"],
                json.dumps(decision["constraints"], sort_keys=True),
                decision["decision"],
            ),
        )
        return int(cur.lastrowid or 0)


def latest_sizing_for(ticker: str) -> dict[str, Any] | None:
    """Return the most recent sizing decision for ``ticker``, or ``None``.

    Used by the paper-trading adapters so they place orders sized by the
    Kelly-lite decision instead of a hardcoded 1 share.
    """
    db.init()
    with db.connect() as cx:
        row = cx.execute(
            "SELECT ticker, decided_at, capped_position_pct, dollar_amount, decision "
            "FROM position_sizing_decisions WHERE ticker = ? "
            "ORDER BY decided_at DESC, id DESC LIMIT 1",
            (ticker.upper(),),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def shares_from_sizing(
    sizing: dict[str, Any] | None,
    last_price: float,
    *,
    fallback_qty: int = 1,
) -> int:
    """Convert a sizing decision into an integer share count.

    - ``None`` or ``decision != 'size'`` -> 0 (skip).
    - Missing/zero price -> ``fallback_qty`` so we degrade gracefully when
      we have a sizing intent but no fresh price.
    """
    if not sizing or sizing.get("decision") != "size":
        return 0
    dollars = float(sizing.get("dollar_amount") or 0.0)
    if dollars <= 0:
        return 0
    if last_price <= 0:
        return fallback_qty
    qty = int(dollars // last_price)
    return qty if qty > 0 else 0
