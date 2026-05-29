"""Streamlit dashboard v2.

Audited fixes:
- Section 1: select sensible columns (was rendering blank with 26 merged cols).
- Section 2: log-scale + outlier clip (SIVE +2300% was squashing all other lines).
- All tables use width='stretch' (replaces deprecated use_container_width).
- @st.cache_data(ttl=60) on every SQL.
- Sidebar with last-updated timestamp + 4 pipeline buttons.
- Color-coded Overall column.
- Ticker drill-down with filings + tweets + insider history.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import db, pair_trade  # noqa: E402

st.set_page_config(page_title="Serenity-Killer", page_icon="🎯", layout="wide")


# ───────── cached loaders ─────────
@st.cache_data(ttl=60)
def load_chokepoints() -> pd.DataFrame:
    db.init()
    with db.connect() as cx:
        return pd.read_sql_query("SELECT * FROM chokepoints ORDER BY ticker", cx)


@st.cache_data(ttl=60)
def load_latest_scores() -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query(
            "SELECT * FROM scores WHERE id IN (SELECT MAX(id) FROM scores GROUP BY ticker)", cx
        )


@st.cache_data(ttl=60)
def load_status() -> dict:
    with db.connect() as cx:
        latest_score = cx.execute("SELECT MAX(scored_at) FROM scores").fetchone()[0]
        latest_run = cx.execute(
            "SELECT command || ':' || status || ' @ ' || COALESCE(finished_at, started_at) "
            "FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        evidence_count = cx.execute("SELECT COUNT(*) FROM evidence_log").fetchone()[0]
        full_bodies = cx.execute("SELECT COUNT(*) FROM filings WHERE length(summary) >= 500").fetchone()[0]
    return {
        "latest_score": latest_score or "never",
        "latest_run": latest_run[0] if latest_run and latest_run[0] else "none",
        "evidence_count": evidence_count,
        "full_bodies": full_bodies,
    }


@st.cache_data(ttl=60)
def load_contamination() -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query("SELECT * FROM contamination", cx)


@st.cache_data(ttl=60)
def load_filings(limit: int = 50) -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query(
            "SELECT ticker, form, title, filed_at, url, keyword_hits FROM filings "
            "ORDER BY discovered_at DESC LIMIT ?",
            cx, params=(limit,),
        )


@st.cache_data(ttl=60)
def load_filings_for_ticker(ticker: str, limit: int = 100) -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query(
            "SELECT form, title, filed_at, url, keyword_hits FROM filings "
            "WHERE ticker = ? ORDER BY filed_at DESC, discovered_at DESC LIMIT ?",
            cx,
            params=(ticker, limit),
        )


@st.cache_data(ttl=60)
def load_tweets(limit: int = 50) -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query(
            "SELECT handle, posted_at, text, tickers, url FROM tweets "
            "WHERE tickers <> '' ORDER BY discovered_at DESC LIMIT ?",
            cx, params=(limit,),
        )


@st.cache_data(ttl=60)
def load_prices() -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query("SELECT ticker, date, close FROM prices ORDER BY date", cx)


@st.cache_data(ttl=60)
def load_insider() -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query(
            "SELECT * FROM insider_txns ORDER BY discovered_at DESC LIMIT 200", cx
        )


@st.cache_data(ttl=60)
def load_positions() -> pd.DataFrame:
    with db.connect() as cx:
        return pd.read_sql_query(
            "SELECT * FROM positions WHERE closed_at IS NULL ORDER BY ticker", cx
        )


# ───────── sidebar ─────────
def _run_cli(cmd: str) -> str:
    try:
        p = subprocess.run(
            [sys.executable, "-m", "src.cli", cmd],
            capture_output=True, text=True, cwd=str(ROOT), timeout=900,
        )
        return ((p.stdout or "") + (p.stderr or "")).splitlines()[-30:]
    except Exception as e:
        return [f"error: {e}"]


with st.sidebar:
    st.markdown("### 🎯 Serenity-Killer")
    st.caption(f"Loaded at: **{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

    if st.button("Refresh prices", width="stretch"):
        with st.spinner("Running `prices`..."):
            tail = _run_cli("prices")
        st.code("\n".join(tail))
        st.cache_data.clear()

    if st.button("Re-score tickers", width="stretch"):
        with st.spinner("Running `score`..."):
            tail = _run_cli("score")
        st.code("\n".join(tail))
        st.cache_data.clear()

    if st.button("Sync paper portfolio", width="stretch"):
        with st.spinner("Syncing positions..."):
            tail = _run_cli("paper")
        st.code("\n".join(tail))
        st.cache_data.clear()

    if st.button("Weekly brief (Claude)", width="stretch"):
        with st.spinner("Asking Claude..."):
            tail = _run_cli("brief")
        st.code("\n".join(tail))

    st.markdown("---")
    st.caption("Full pipeline (~3-5 min): `py -m src.cli all`")


# ───────── main ─────────
st.title("🎯 Serenity-Killer Playbook — Live Dashboard")

cp = load_chokepoints()
sc = load_latest_scores()
ct = load_contamination()
fl = load_filings()
tw = load_tweets()
prices_long = load_prices()
positions = load_positions()
insider = load_insider()
status = load_status()

# Header KPIs
buys = int((sc["overall"] == "Buy").sum()) if not sc.empty else 0
watches = int((sc["overall"] == "Watch").sum()) if not sc.empty else 0
passes = int((sc["overall"] == "Pass").sum()) if not sc.empty else 0
skips = int((sc["overall"] == "Skip").sum()) if not sc.empty else 0
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tracked tickers", len(cp))
c2.metric("🟢 Buy", buys)
c3.metric("🟡 Watch", watches)
c4.metric("🔴 Pass (contaminated)", passes)
c5.metric("⚪ Skip", skips)

s1, s2, s3, s4 = st.columns(4)
s1.metric("Latest score", status["latest_score"])
s2.metric("Latest run", status["latest_run"])
s3.metric("Evidence rows", status["evidence_count"])
s4.metric("Full filing bodies", status["full_bodies"])

# Section 1
st.header("1) Chokepoint master + crowd contamination")
if cp.empty:
    st.info("Run `py -m src.cli seed`.")
else:
    merged = cp.merge(ct, on="ticker", how="left", suffixes=("", "_ct"))
    display_cols = [c for c in [
        "ticker", "chokepoint", "end_customer", "evidence_grade",
        "market_cap_usd", "ev_sales", "next_catalyst", "catalyst_score",
        "crowd_flag", "last_close", "pct_change_5d", "pct_change_20d",
        "volume_ratio_20d", "decision",
    ] if c in merged.columns]
    st.dataframe(
        merged[display_cols], width="stretch", height=420,
        column_config={
            "market_cap_usd": st.column_config.NumberColumn(format="$%.0f"),
            "ev_sales": st.column_config.NumberColumn(format="%.1fx"),
            "catalyst_score": st.column_config.ProgressColumn(min_value=0, max_value=10, format="%d"),
            "pct_change_5d": st.column_config.NumberColumn(format="%+.1f%%"),
            "pct_change_20d": st.column_config.NumberColumn(format="%+.1f%%"),
            "volume_ratio_20d": st.column_config.NumberColumn(format="%.2fx"),
        },
    )

# Section 2 — fixed chart
st.header("2) Top movers (normalized close, last 90d)")
if prices_long.empty or ct.empty:
    st.info("Run `py -m src.cli prices`.")
else:
    plot_prices = prices_long.copy()
    plot_prices["date"] = pd.to_datetime(plot_prices["date"], errors="coerce")
    plot_prices = plot_prices.dropna(subset=["date", "close"])
    pivot = plot_prices.pivot_table(index="date", columns="ticker", values="close", aggfunc="last")
    valid = [t for t in pivot.columns if pivot[t].dropna().shape[0] >= 5]
    pivot = pivot[valid]
    default_top = (
        ct.dropna(subset=["pct_change_20d"])
        .reindex(ct["pct_change_20d"].abs().sort_values(ascending=False).index)
        .head(6)["ticker"].tolist()
    )
    default_top = [t for t in default_top if t in valid] or valid[:6]

    a, b = st.columns([3, 1])
    with b:
        chosen = st.multiselect("Tickers", sorted(valid), default=default_top, max_selections=12)
        log_scale = st.checkbox("Log scale", value=True)
        clip_pct = st.slider("Clip extremes at percentile", 90, 100, 99)

    if chosen:
        sub = pivot[chosen].dropna(how="all")
        normed = sub.apply(lambda c: 100.0 * c / c.dropna().iloc[0] if c.dropna().shape[0] else c)
        upper = float(np.nanpercentile(normed.values, clip_pct))
        normed = normed.clip(upper=upper)
        if log_scale:
            normed = normed.where(normed > 0)
            normed = normed.apply(np.log10)
        normed = normed.replace([np.inf, -np.inf], np.nan).dropna(how="all")
        with a:
            st.caption(
                f"{'Log10 of normalized' if log_scale else 'Normalized'} close (base=100). "
                f"Outliers clipped at p{clip_pct}={upper:.1f}."
            )
            if normed.empty:
                st.info("No plottable price data for the selected tickers.")
            else:
                chart_df = normed.reset_index().melt("date", var_name="ticker", value_name="value").dropna()
                chart = (
                    alt.Chart(chart_df)
                    .mark_line()
                    .encode(
                        x=alt.X("date:T", title="Date"),
                        y=alt.Y("value:Q", title="Log10 normalized close" if log_scale else "Normalized close"),
                        color=alt.Color("ticker:N", title="Ticker"),
                        tooltip=["ticker:N", "date:T", alt.Tooltip("value:Q", format=".2f")],
                    )
                    .properties(height=360)
                )
                st.altair_chart(chart, width="stretch")
    else:
        with a:
            st.info("Pick at least one ticker.")

# Section 3 — color-coded scoring
st.header("3) Latest scoring snapshot")
if sc.empty:
    st.info("Run `py -m src.cli score`.")
else:
    score_cols = [c for c in sc.columns if c not in ("id", "scored_at", "notes")]
    ordered = sc[score_cols].sort_values(
        "overall", key=lambda s: s.map({"Buy": 0, "Watch": 1, "Pass": 2, "Skip": 3}),
    )

    def _color(val):
        return {
            "Buy": "background-color: #d1fae5",
            "Watch": "background-color: #fef3c7",
            "Pass": "background-color: #fee2e2",
            "Skip": "background-color: #e5e7eb",
        }.get(val, "")

    styled = ordered.style.map(_color, subset=["overall"])
    st.dataframe(styled, width="stretch", height=360)

# Section 4 — pair trades
st.header("4) Pair-trade candidates")
pairs = pd.DataFrame(pair_trade.candidates())
if pairs.empty:
    st.info("No pair candidates yet — needs 20-day price data.")
else:
    st.dataframe(
        pairs, width="stretch",
        column_config={
            "long_20d": st.column_config.NumberColumn(format="%+.1f%%"),
            "short_20d": st.column_config.NumberColumn(format="%+.1f%%"),
            "spread_pct": st.column_config.NumberColumn(format="%+.1f%%"),
        },
    )

# Section 5 — open positions
st.header("5) Open paper positions")
if positions.empty:
    st.info("Run `py -m src.cli paper`.")
else:
    st.dataframe(
        positions, width="stretch",
        column_config={
            "cost_basis": st.column_config.NumberColumn(format="$%.2f"),
            "last_price": st.column_config.NumberColumn(format="$%.2f"),
            "pnl_pct": st.column_config.NumberColumn(format="%+.1f%%"),
        },
    )

# Section 6 — ticker drill-down
st.header("6) Ticker drill-down")
if not cp.empty:
    pick = st.selectbox("Pick a ticker", cp["ticker"].tolist())
    a, b, c = st.columns(3)
    with a:
        st.markdown("**Filings**")
        sub = load_filings_for_ticker(pick)
        if sub.empty:
            st.caption(f"No filings hit for {pick}")
        else:
            st.dataframe(
                sub,
                width="stretch",
                height=240,
                column_config={"url": st.column_config.LinkColumn("link")},
            )
    with b:
        st.markdown("**Tweet mentions**")
        sub = tw[tw["tickers"].str.contains(pick, na=False)] if not tw.empty else pd.DataFrame()
        if sub.empty:
            st.caption(f"No tweets cashtagged {pick}")
        else:
            st.dataframe(sub, width="stretch", height=240)
    with c:
        st.markdown("**Insider Form 4**")
        sub = insider[insider["ticker"] == pick] if not insider.empty else pd.DataFrame()
        if sub.empty:
            st.caption(f"No insider txns for {pick}")
        else:
            st.dataframe(sub, width="stretch", height=240)

# Section 7 — full lists in expanders
with st.expander("📰 Recent keyword-hit filings (full)"):
    if fl.empty:
        st.info("Run `py -m src.cli harvest`.")
    else:
        st.dataframe(
            fl, width="stretch", height=400,
            column_config={"url": st.column_config.LinkColumn("link")},
        )

with st.expander("🐦 Smart-money tweets (full)"):
    if tw.empty:
        st.info("Run `py -m src.cli tweets`.")
    else:
        st.dataframe(
            tw, width="stretch", height=400,
            column_config={"url": st.column_config.LinkColumn("link")},
        )
