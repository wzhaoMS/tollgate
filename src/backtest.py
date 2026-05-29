"""Backtest harness.

Walks the prices table day by day for each ticker, computes the contamination
flag *as of that day*, then derives a synthetic decision. Compares that
historical decision to what actually happened over the next 5 / 20 / 60 trading
days. Writes a per-decision hit-rate report.

This is a v0: it only backtests the Step -1 (crowd contamination) decision,
because Steps 1/8/9 require static metadata. It's still useful: it tells you
how well the contamination flag predicts forward returns.
"""
from __future__ import annotations
import statistics
from dataclasses import dataclass
from typing import Iterable

from . import db


@dataclass
class WindowResult:
    ticker: str
    as_of: str
    crowd_flag: str
    pct_5d_prior: float | None
    pct_20d_prior: float | None
    fwd_5d: float | None
    fwd_20d: float | None
    fwd_60d: float | None


def _walk_prices(cx, ticker: str) -> list[dict]:
    rows = cx.execute(
        "SELECT date, close FROM prices WHERE ticker = ? ORDER BY date ASC",
        (ticker.upper(),),
    ).fetchall()
    return [{"date": r["date"], "close": r["close"]} for r in rows if r["close"]]


def _pct(later: float, earlier: float) -> float | None:
    if earlier is None or earlier == 0 or later is None:
        return None
    return (later - earlier) / earlier * 100.0


def _flag(p5: float | None, p20: float | None) -> str:
    if p5 is not None and (p5 >= 20) or p20 is not None and (p20 >= 50):
        return "high"
    if p5 is not None and (p5 >= 10) or p20 is not None and (p20 >= 25):
        return "medium"
    return "low"


def backtest_ticker(cx, ticker: str) -> list[WindowResult]:
    series = _walk_prices(cx, ticker)
    n = len(series)
    if n < 40:
        return []
    out: list[WindowResult] = []
    # Use as much forward window as available (cap at 60), but also accept smaller forwards.
    fwd_max = min(60, max(5, n // 3))
    for i in range(20, n - 5):
        today = series[i]
        prior_5 = series[i - 5]["close"] if i - 5 >= 0 else None
        prior_20 = series[i - 20]["close"] if i - 20 >= 0 else None
        fwd_5 = series[i + 5]["close"] if i + 5 < n else None
        fwd_20 = series[i + 20]["close"] if i + 20 < n else None
        fwd_60 = series[i + fwd_max]["close"] if i + fwd_max < n else None
        p5 = _pct(today["close"], prior_5)
        p20 = _pct(today["close"], prior_20)
        flag = _flag(p5, p20)
        out.append(
            WindowResult(
                ticker=ticker.upper(),
                as_of=today["date"],
                crowd_flag=flag,
                pct_5d_prior=p5,
                pct_20d_prior=p20,
                fwd_5d=_pct(fwd_5, today["close"]),
                fwd_20d=_pct(fwd_20, today["close"]),
                fwd_60d=_pct(fwd_60, today["close"]),
            )
        )
    return out


def aggregate(results: Iterable[WindowResult]) -> dict:
    by_flag: dict[str, list[WindowResult]] = {"low": [], "medium": [], "high": []}
    for r in results:
        by_flag.setdefault(r.crowd_flag, []).append(r)
    out: dict = {}
    for flag, rows in by_flag.items():
        if not rows:
            out[flag] = {"n": 0}
            continue

        def _stats(values: list[float | None]) -> dict:
            xs = [v for v in values if v is not None]
            if not xs:
                return {"n": 0}
            return {
                "n": len(xs),
                "mean": statistics.mean(xs),
                "median": statistics.median(xs),
                "p_up": sum(1 for v in xs if v > 0) / len(xs),
            }

        out[flag] = {
            "n": len(rows),
            "fwd_5d": _stats([r.fwd_5d for r in rows]),
            "fwd_20d": _stats([r.fwd_20d for r in rows]),
            "fwd_60d": _stats([r.fwd_60d for r in rows]),
        }
    return out


def main() -> None:
    db.init()
    all_rows: list[WindowResult] = []
    with db.connect() as cx:
        tickers = [r[0] for r in cx.execute("SELECT DISTINCT ticker FROM prices")]
        for t in tickers:
            all_rows.extend(backtest_ticker(cx, t))
    if not all_rows:
        print("No price history yet — run `prices` first and let it accumulate.")
        return
    summary = aggregate(all_rows)
    print(f"Backtested {len(all_rows)} (ticker, day) windows across {len(tickers)} tickers.\n")
    for flag in ("low", "medium", "high"):
        s = summary.get(flag, {"n": 0})
        if not s.get("n"):
            continue
        print(f"crowd_flag = {flag.upper()}  (n={s['n']})")
        for k in ("fwd_5d", "fwd_20d", "fwd_60d"):
            sub = s.get(k, {})
            if sub.get("n"):
                print(
                    f"  {k}: n={sub['n']}, mean={sub['mean']:+.2f}%, "
                    f"median={sub['median']:+.2f}%, p_up={sub['p_up']:.1%}"
                )
        print()


if __name__ == "__main__":
    main()
