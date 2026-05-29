"""Streamlit dashboard. Run: streamlit run src/dashboard.py"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# allow running as `streamlit run src/dashboard.py`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import db, pair_trade  # noqa: E402

st.set_page_config(page_title="Serenity-Killer", layout="wide")
st.title("Serenity-Killer Playbook — Live Dashboard")

db.init()

with db.connect() as cx:
    cp = pd.read_sql_query("SELECT * FROM chokepoints ORDER BY ticker", cx)
    sc = pd.read_sql_query(
        "SELECT * FROM scores WHERE id IN "
        "(SELECT MAX(id) FROM scores GROUP BY ticker)",
        cx,
    )
    ct = pd.read_sql_query("SELECT * FROM contamination", cx)
    fl = pd.read_sql_query(
        "SELECT form, title, filed_at, url, keyword_hits FROM filings "
        "ORDER BY discovered_at DESC LIMIT 50",
        cx,
    )
    tw = pd.read_sql_query(
        "SELECT handle, posted_at, text, tickers, url FROM tweets "
        "WHERE tickers <> '' ORDER BY discovered_at DESC LIMIT 50",
        cx,
    )
    prices_long = pd.read_sql_query(
        "SELECT ticker, date, close, volume FROM prices ORDER BY date",
        cx,
    )

# ---- Header KPIs ----
buys = (sc["overall"] == "Buy").sum() if not sc.empty else 0
watches = (sc["overall"] == "Watch").sum() if not sc.empty else 0
passes = (sc["overall"] == "Pass").sum() if not sc.empty else 0
col1, col2, col3, col4 = st.columns(4)
col1.metric("Tracked tickers", len(cp))
col2.metric("Buy", int(buys))
col3.metric("Watch", int(watches))
col4.metric("Pass (contaminated)", int(passes))

# ---- Section 1: Chokepoint master table ----
st.header("1) Chokepoint master + crowd contamination")
merged = cp.merge(ct, on="ticker", how="left")
st.dataframe(merged, use_container_width=True, height=400)

# ---- Section 2: Top movers chart ----
st.header("2) Top movers (last 90d close)")
if not prices_long.empty:
    pivot = prices_long.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    )
    if not ct.empty:
        top = (
            ct.dropna(subset=["pct_change_20d"])
            .reindex(ct["pct_change_20d"].abs().sort_values(ascending=False).index)
            .head(8)
        )
        top_tickers = [t for t in top["ticker"] if t in pivot.columns]
        if top_tickers:
            # Normalize to 100 at start
            norm = pivot[top_tickers].dropna(how="all").apply(
                lambda c: 100.0 * c / c.dropna().iloc[0] if c.dropna().shape[0] else c
            )
            st.line_chart(norm)
        else:
            st.write("No overlap between contamination + price tickers yet.")
    else:
        st.write("Run `py -m src.cli prices` to populate contamination.")
else:
    st.write("No price history. Run `py -m src.cli prices`.")

# ---- Section 3: Scoring snapshot ----
st.header("3) Latest scoring snapshot")
st.dataframe(sc, use_container_width=True)

# ---- Section 4: Pair-trade candidates ----
st.header("4) Pair-trade candidates")
pairs = pd.DataFrame(pair_trade.candidates())
st.dataframe(pairs, use_container_width=True)

# ---- Section 5: Recent filings ----
st.header("5) Recent keyword-hit filings")
st.dataframe(fl, use_container_width=True, height=300)

# ---- Section 6: Tweets with cashtags ----
st.header("6) Smart-money tweets with cashtags")
st.dataframe(tw, use_container_width=True, height=300)
