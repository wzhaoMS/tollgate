"""Alpaca paper trading adapter.

Reads ALPACA_KEY / ALPACA_SECRET from .env. Submits paper orders for tickers
currently scored 'Buy' that we don't already hold, and closes positions whose
score has dropped or whose drawdown trigger has fired.

Position size comes from the latest row in ``position_sizing_decisions``
(see ``src.risk_sizing``). If no sizing decision exists for a ticker we fall
back to a single share so the existing local-paper behavior is preserved.
"""
from __future__ import annotations

import os

import requests

from . import db, paper, risk_sizing, scoring

ALPACA_BASE = os.environ.get("ALPACA_BASE", "https://paper-api.alpaca.markets")
KEY = os.environ.get("ALPACA_KEY", "").strip()
SECRET = os.environ.get("ALPACA_SECRET", "").strip()


def _headers() -> dict[str, str]:
    return {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}


def _ready() -> bool:
    return bool(KEY and SECRET)


def list_positions() -> list[dict]:
    if not _ready():
        return []
    r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=_headers(), timeout=20)
    if not r.ok:
        return []
    return r.json()


def submit_market_order(ticker: str, qty: float, side: str = "buy") -> dict | None:
    if not _ready():
        return None
    body = {
        "symbol": ticker.upper(),
        "qty": qty,
        "side": side,
        "type": "market",
        "time_in_force": "day",
    }
    r = requests.post(f"{ALPACA_BASE}/v2/orders", json=body, headers=_headers(), timeout=20)
    if not r.ok:
        print(f"  alpaca order failed [{r.status_code}]: {r.text[:200]}")
        return None
    return r.json()


def sync(action_log: bool = True) -> dict:
    """Reconcile scoring decisions with paper portfolio:
       - Open 1 share for any 'Buy' ticker we don't already hold.
       - Close any position whose latest score is no longer 'Buy'.
    """
    db.init()
    results = {"opened": [], "closed": [], "skipped": []}
    if not _ready():
        # Fall back to internal paper module
        return _sync_internal()
    open_now = {p["symbol"]: p for p in list_positions()}
    scores = {r["ticker"]: r["overall"] for r in scoring.latest_scores()}
    last_close = _last_close_map()
    for ticker, overall in scores.items():
        if overall == "Buy" and ticker not in open_now:
            sizing = risk_sizing.latest_sizing_for(ticker)
            qty = risk_sizing.shares_from_sizing(sizing, last_close.get(ticker, 0.0))
            if qty <= 0 and sizing is None:
                qty = 1  # backward-compatible default
            if qty <= 0:
                results["skipped"].append(ticker)
                continue
            o = submit_market_order(ticker, qty, "buy")
            if o:
                results["opened"].append(ticker)
                # mirror locally
                paper.open_position(ticker, qty, last_close.get(ticker, 0.0), notes="alpaca-paper")
        elif overall != "Buy" and ticker in open_now:
            o = submit_market_order(ticker, open_now[ticker]["qty"], "sell")
            if o:
                results["closed"].append(ticker)
                paper.close_position(ticker)
        else:
            results["skipped"].append(ticker)
    if action_log:
        print(f"alpaca sync: opened={results['opened']}, closed={results['closed']}")
    return results


def _last_close_map() -> dict[str, float]:
    out: dict[str, float] = {}
    with db.connect() as cx:
        for r in cx.execute(
            "SELECT ticker, last_close FROM contamination WHERE last_close IS NOT NULL"
        ):
            out[r["ticker"]] = float(r["last_close"])
    return out


def _sync_internal() -> dict:
    """No Alpaca creds — just maintain the local `positions` table.
    Uses the most recent close (from contamination/prices) as cost basis,
    and the latest Kelly-lite sizing decision for share count.
    """
    results = {"opened": [], "closed": [], "skipped": []}
    held = {p["ticker"] for p in paper.list_positions()}
    scores = {r["ticker"]: r["overall"] for r in scoring.latest_scores()}
    last_close = _last_close_map()
    for ticker, overall in scores.items():
        if overall == "Buy" and ticker not in held:
            cost = last_close.get(ticker, 0.0)
            sizing = risk_sizing.latest_sizing_for(ticker)
            qty = risk_sizing.shares_from_sizing(sizing, cost)
            if qty <= 0 and sizing is None:
                qty = 1  # backward-compatible default
            if qty <= 0:
                results["skipped"].append(ticker)
                continue
            paper.open_position(ticker, qty, cost, notes="local-paper")
            results["opened"].append(ticker)
        elif overall != "Buy" and ticker in held:
            paper.close_position(ticker)
            results["closed"].append(ticker)
        else:
            results["skipped"].append(ticker)
    print(
        f"local-paper sync (no Alpaca creds): "
        f"opened={results['opened']}, closed={results['closed']}"
    )
    return results


def main() -> None:
    sync()


if __name__ == "__main__":
    main()
