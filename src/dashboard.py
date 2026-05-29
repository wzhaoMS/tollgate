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

st.header("Chokepoint database")
st.dataframe(cp.merge(ct, on="ticker", how="left"), use_container_width=True)

st.header("Latest scoring snapshot")
st.dataframe(sc, use_container_width=True)

st.header("Pair-trade candidates")
st.dataframe(pd.DataFrame(pair_trade.candidates()), use_container_width=True)

st.header("Recent keyword-hit filings")
st.dataframe(fl, use_container_width=True)

st.header("Smart-money tweets with cashtags")
st.dataframe(tw, use_container_width=True)
