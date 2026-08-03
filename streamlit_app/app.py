"""
StreamPulse — Dashboard (Phase 3.2)

Live view: row counts, recent orders, and a structured Alerts panel
sourced from dbt's unified alerts model (data quality + anomaly detection).
"""

import os

import duckdb
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/orders.duckdb")

st.set_page_config(page_title="StreamPulse", page_icon="📦", layout="wide")
st.title("📦 StreamPulse")
st.caption("Near-real-time e-commerce order analytics")

if not os.path.exists(DUCKDB_PATH):
    st.warning(
        f"No database found at `{DUCKDB_PATH}`.\n\n"
        "This is expected on the public deployment — the pipeline runs "
        "locally on the developer's machine and hasn't been connected to "
        "a shared/cloud data store yet."
    )
    st.stop()

con = duckdb.connect(DUCKDB_PATH, read_only=True)

tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}

col1, col2, col3 = st.columns(3)

with col1:
    bronze_count = con.execute("SELECT COUNT(*) FROM bronze_orders").fetchone()[0]
    st.metric("Orders landed", bronze_count)

with col2:
    rejected_count = con.execute("SELECT COUNT(*) FROM rejected_events").fetchone()[0]
    st.metric("Rejected events", rejected_count)

with col3:
    if "alerts" in tables:
        alert_count = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        st.metric("Active alerts", alert_count)
    else:
        st.metric("Active alerts", "—")

st.divider()

if "alerts" in tables:
    st.subheader("🚨 Alerts")
    alerts = con.execute(
        """
        SELECT alert_timestamp, severity, region, alert_type, reason
        FROM alerts
        ORDER BY alert_timestamp DESC
        LIMIT 20
        """
    ).fetchdf()

    if len(alerts) == 0:
        st.success("No active alerts.")
    else:
        def highlight_severity(row):
            color = "#5c1a1a" if row["severity"] == "warning" else "#1a3a5c"
            return [f"background-color: {color}"] * len(row)

        st.dataframe(
            alerts.style.apply(highlight_severity, axis=1),
            width="stretch",
        )
else:
    st.info("Alerts model not yet built. Run `dbt run` in the `dbt/` folder.")

st.divider()

st.subheader("Recent orders")
if "silver_orders" in tables:
    recent = con.execute(
        """
        SELECT order_id, product_name, region, unit_price, quantity, order_total, event_timestamp
        FROM silver_orders
        ORDER BY event_timestamp DESC
        LIMIT 10
        """
    ).fetchdf()
else:
    recent = con.execute(
        """
        SELECT order_id, product_name, region, price, quantity, event_timestamp
        FROM bronze_orders
        ORDER BY ingested_at DESC
        LIMIT 10
        """
    ).fetchdf()

st.dataframe(recent, width="stretch")

con.close()
