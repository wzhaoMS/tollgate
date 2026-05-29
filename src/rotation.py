"""Sector rotation map: theme stages + upstream links + relative-strength signal.

Implements Layer 1 of the first-principles checklist. The chain we track is:

    HBM/memory  ->  optical transceivers  ->  CPO + external lasers  ->
    foundry/substrates  ->  ???

Two SQL-backed concepts:

- ``theme_rotation_stages`` orders our chokepoint themes from "obvious /
  already crowded" (low stage index) to "still undiscovered" (high stage
  index). Plus a list of canonical tickers per stage.
- ``upstream_links`` records that money flowing into ``downstream_theme`` is
  *predicted* to roll into ``upstream_theme`` next.

The ``compute_rotation_signal`` helper looks at recent price action per stage
and flags a rotation event when stage N's 20d return rolls over while
stage N+1's 20d return turns up.
"""
from __future__ import annotations

from . import db

BUILTIN_STAGES: list[dict] = [
    {"theme": "HBM/memory",            "stage_idx": 0, "tickers": "MU,SNDK,STX,WDC"},
    {"theme": "optical_transceivers",  "stage_idx": 1, "tickers": "AAOI,LITE,COHR,CIEN"},
    {"theme": "CPO/external_lasers",   "stage_idx": 2, "tickers": "SIVE,POET,CRDO,ALAB"},
    {"theme": "foundry/substrates",    "stage_idx": 3, "tickers": "XFAB,SOI,IQE,AXTI"},
    {"theme": "power/grid",            "stage_idx": 4, "tickers": "HPS-A,WOLF,NVTS,POWI,CEG,VST"},
]

BUILTIN_UPSTREAM_LINKS: list[tuple[str, str, float]] = [
    ("HBM/memory",            "optical_transceivers", 0.8),
    ("optical_transceivers",  "CPO/external_lasers",  0.85),
    ("CPO/external_lasers",   "foundry/substrates",   0.9),
    ("foundry/substrates",    "power/grid",           0.6),
]


def init() -> None:
    db.init()
    with db.connect() as cx:
        cx.executescript(
            """
            CREATE TABLE IF NOT EXISTS theme_rotation_stages (
                theme       TEXT PRIMARY KEY,
                stage_idx   INTEGER NOT NULL,
                tickers     TEXT,
                updated_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS upstream_links (
                downstream_theme TEXT NOT NULL,
                upstream_theme   TEXT NOT NULL,
                strength         REAL DEFAULT 0.5,
                updated_at       TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (downstream_theme, upstream_theme)
            );
            """
        )


def import_builtin_stages() -> int:
    init()
    n = 0
    with db.connect() as cx:
        for s in BUILTIN_STAGES:
            cur = cx.execute(
                "INSERT INTO theme_rotation_stages (theme, stage_idx, tickers) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(theme) DO UPDATE SET stage_idx = excluded.stage_idx, "
                "tickers = excluded.tickers, updated_at = datetime('now')",
                (s["theme"], int(s["stage_idx"]), s["tickers"]),
            )
            n += cur.rowcount or 0
        for downstream, upstream, strength in BUILTIN_UPSTREAM_LINKS:
            cx.execute(
                "INSERT INTO upstream_links (downstream_theme, upstream_theme, strength) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(downstream_theme, upstream_theme) DO UPDATE SET "
                "strength = excluded.strength, updated_at = datetime('now')",
                (downstream, upstream, float(strength)),
            )
    return n


def _stage_return_20d(cx, tickers: list[str]) -> float | None:
    """Average of ``pct_change_20d`` from the contamination table."""
    if not tickers:
        return None
    placeholders = ",".join("?" for _ in tickers)
    rows = cx.execute(
        f"SELECT pct_change_20d FROM contamination "
        f"WHERE ticker IN ({placeholders}) AND pct_change_20d IS NOT NULL",
        tickers,
    ).fetchall()
    values = [float(r["pct_change_20d"]) for r in rows]
    if not values:
        return None
    return sum(values) / len(values)


def compute_rotation_signal() -> list[dict]:
    """Return a per-stage signal list ordered by stage_idx.

    For each stage we report the average 20d return and a textual signal:

    - ``hot``        20d return > +10%
    - ``rolling``    20d return between 0% and +10%
    - ``cold``       20d return between -10% and 0%
    - ``unwinding``  20d return < -10%
    - ``unknown``    no price data

    A separate field ``rotation_to_next`` flags when stage N is unwinding
    while stage N+1 is hot — that's the literal "money rolled to the next
    stop" Serenity describes.
    """
    init()
    with db.connect() as cx:
        stages = [dict(r) for r in cx.execute(
            "SELECT theme, stage_idx, tickers FROM theme_rotation_stages ORDER BY stage_idx"
        )]
    out = []
    returns: dict[int, float | None] = {}
    with db.connect() as cx:
        for s in stages:
            tickers = [t.strip().upper() for t in (s["tickers"] or "").split(",") if t.strip()]
            ret = _stage_return_20d(cx, tickers)
            returns[s["stage_idx"]] = ret
            if ret is None:
                signal = "unknown"
            elif ret > 10:
                signal = "hot"
            elif ret >= 0:
                signal = "rolling"
            elif ret > -10:
                signal = "cold"
            else:
                signal = "unwinding"
            out.append({
                "theme": s["theme"],
                "stage_idx": s["stage_idx"],
                "avg_return_20d_pct": ret,
                "signal": signal,
            })
    for entry in out:
        idx = entry["stage_idx"]
        nxt = returns.get(idx + 1)
        cur = returns.get(idx)
        entry["rotation_to_next"] = bool(
            cur is not None and nxt is not None and cur <= 0 and nxt >= 5
        )
    return out


def main() -> None:
    import_builtin_stages()
    for s in compute_rotation_signal():
        ret = s["avg_return_20d_pct"]
        ret_str = f"{ret:+.1f}%" if ret is not None else "n/a"
        flag = " *ROTATE*" if s["rotation_to_next"] else ""
        print(f"stage {s['stage_idx']} {s['theme']:<22} 20d={ret_str:<8} {s['signal']}{flag}")


if __name__ == "__main__":
    main()
