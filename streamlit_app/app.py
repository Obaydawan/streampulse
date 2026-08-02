"""
StreamPulse — Minimal Dashboard (Phase 2.4)

Bare-bones live view: row counts from the DuckDB bronze layer.
Deliberately simple — this exists to surface deployment issues early
while the system is still small, per the project's deployment strategy.
"""

import os

import duckdb
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/orders.duckdb")

st.set_page_config(page_title="StreamPulse", page_icon="📦", layout="centered")
st.title("📦 StreamPulse")
st.caption("Near-real-time e-commerce order analytics — Phase 2.4 minimal view")

if not os.path.exists(DUCKDB_PATH):
    st.warning(
        f"No database found at `{DUCKDB_PATH}`.\n\n"
        "This is expected on the public deployment — the pipeline runs "
        "locally on the developer's machine and hasn't been connected to "
        "a shared/cloud data store yet. This page proves the deployment "
        "path itself works, ahead of that being wired up in a later phase."
    )
    st.stop()

con = duckdb.connect(DUCKDB_PATH, read_only=True)

col1, col2 = st.columns(2)

with col1:
    bronze_count = con.execute("SELECT COUNT(*) FROM bronze_orders").fetchone()[0]
    st.metric("Orders landed", bronze_count)

with col2:
    rejected_count = con.execute("SELECT COUNT(*) FROM rejected_events").fetchone()[0]
    st.metric("Rejected events", rejected_count)

st.subheader("Recent orders")
recent = con.execute(
    """
    SELECT order_id, product_name, region, price, quantity, event_timestamp
    FROM bronze_orders
    ORDER BY ingested_at DESC
    LIMIT 10
    """
).fetchdf()
st.dataframe(recent, width='stretch')

if rejected_count > 0:
    st.subheader("Recent rejected events")
    rejected = con.execute(
        "SELECT reason, rejected_at FROM rejected_events ORDER BY rejected_at DESC LIMIT 5"
    ).fetchdf()
    st.dataframe(rejected, width='stretch')

con.close()
