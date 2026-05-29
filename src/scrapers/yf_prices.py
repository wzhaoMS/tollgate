"""Pull daily close/volume via yfinance; compute crowd-contamination flag.

Crowd flag logic (Step -1 of the playbook, automated):
  high   => 5d_pct >= 20%  OR  20d_pct >= 50%  OR  volume_ratio_20d >= 5
  medium => 5d_pct >= 10%  OR  20d_pct >= 25%  OR  volume_ratio_20d >= 2
  low    => otherwise
"""
from __future__ import annotations
import time
from datetime import date, timedelta
from typing import Iterable

from .. import db

# Internal ticker -> Yahoo Finance symbol overrides for foreign listings.
TICKER_OVERRIDES: dict[str, str] = {
    "SIVE": "SIVE.ST",
    "SOI": "SOI.PA",
    "XFAB": "XFAB.F",   # Frankfurt floor often more available than Xetra DE for X-FAB
    "IQE": "IQE.L",
    "ALRIB": "ALRIB.PA",
    "LPK": "LPK.DE",
    "RPI": "RPI.L",
    "HPS-A": "HPS-A.TO",
}


def _yf():
    import yfinance as yf
    return yf


def update_prices(ticker: str, lookback_days: int = 90) -> int:
    yf = _yf()
    symbol = TICKER_OVERRIDES.get(ticker.upper(), ticker.upper())
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    hist = yf.Ticker(symbol).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
    if hist is None or hist.empty:
        return 0
    rows_added = 0
    with db.connect() as cx:
        for ts, row in hist.iterrows():
            cx.execute(
                "INSERT OR REPLACE INTO prices (ticker, date, close, volume) VALUES (?, ?, ?, ?)",
                (
                    ticker.upper(),
                    ts.date().isoformat(),
                    float(row["Close"]) if row["Close"] == row["Close"] else None,
                    float(row["Volume"]) if row["Volume"] == row["Volume"] else None,
                ),
            )
            rows_added += 1
    return rows_added


def compute_contamination(ticker: str) -> dict | None:
    """Compute crowd-contamination metrics for a ticker from the prices table."""
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT date, close, volume FROM prices WHERE ticker = ? ORDER BY date DESC LIMIT 30",
            (ticker.upper(),),
        ).fetchall()
    if len(rows) < 5:
        return None

    closes = [r["close"] for r in rows if r["close"] is not None]
    volumes = [r["volume"] for r in rows if r["volume"] is not None]
    if not closes:
        return None

    last_close = closes[0]
    close_5d_ago = closes[min(5, len(closes) - 1)]
    close_20d_ago = closes[min(20, len(closes) - 1)]
    pct_5d = (last_close - close_5d_ago) / close_5d_ago * 100 if close_5d_ago else None
    pct_20d = (last_close - close_20d_ago) / close_20d_ago * 100 if close_20d_ago else None

    vol_20d_avg = sum(volumes[1:21]) / max(1, len(volumes[1:21])) if len(volumes) > 1 else None
    last_volume = volumes[0] if volumes else None
    vol_ratio = (last_volume / vol_20d_avg) if (vol_20d_avg and last_volume and vol_20d_avg > 0) else None

    def _flag() -> str:
        if (pct_5d is not None and pct_5d >= 20) or (pct_20d is not None and pct_20d >= 50) or (vol_ratio is not None and vol_ratio >= 5):
            return "high"
        if (pct_5d is not None and pct_5d >= 10) or (pct_20d is not None and pct_20d >= 25) or (vol_ratio is not None and vol_ratio >= 2):
            return "medium"
        return "low"

    flag = _flag()
    result = {
        "ticker": ticker.upper(),
        "last_close": last_close,
        "pct_change_5d": pct_5d,
        "pct_change_20d": pct_20d,
        "volume_ratio_20d": vol_ratio,
        "crowd_flag": flag,
    }
    with db.connect() as cx:
        cx.execute(
            "INSERT OR REPLACE INTO contamination "
            "(ticker, last_close, pct_change_5d, pct_change_20d, volume_ratio_20d, crowd_flag) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (result["ticker"], last_close, pct_5d, pct_20d, vol_ratio, flag),
        )
        cx.execute(
            "UPDATE chokepoints SET crowdedness = ? WHERE ticker = ?",
            (flag, ticker.upper()),
        )
    return result


def refresh_all() -> list[dict]:
    db.init()
    with db.connect() as cx:
        tickers = [r[0] for r in cx.execute("SELECT ticker FROM chokepoints")]
    out: list[dict] = []
    for t in tickers:
        try:
            n = update_prices(t)
            if n == 0:
                print(f"  [skip] {t}: no price data")
                continue
            m = compute_contamination(t)
            if m:
                out.append(m)
                print(
                    f"  {t}: close={m['last_close']:.2f} 5d={m['pct_change_5d']:.1f}% "
                    f"20d={m['pct_change_20d']:.1f}% volR={m['volume_ratio_20d']:.2f} -> {m['crowd_flag']}"
                )
        except Exception as e:  # noqa: BLE001
            print(f"  [err] {t}: {e}")
        time.sleep(0.4)  # polite
    return out


def main() -> None:
    out = refresh_all()
    print(f"Refreshed prices + contamination for {len(out)} tickers.")


if __name__ == "__main__":
    main()
