"""
StreamPulse — Combined Dashboard (Phase 3.2) + AI Query Agent (Phase 5)

Two tabs in one page:
  - Dashboard: live metrics, Alerts panel, recent orders
  - AI Query Agent: natural language -> Gemini -> SQL -> guardrails -> results
"""

import os
import sys

import duckdb
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_agent.executor import execute_question
from ai_agent.guardrails import GuardrailViolation

load_dotenv()

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/orders.duckdb")
MOTHERDUCK_TOKEN = os.getenv("MOTHERDUCK_TOKEN") or st.secrets.get("MOTHERDUCK_TOKEN", None)
UNABLE_TO_ANSWER_MARKER = "unable to answer using available data"


def get_connection(read_only: bool = True):
    """
    Prefer MotherDuck (cloud) if a token is available. Falls back to the
    local file if MotherDuck is unavailable or the connection fails for
    any reason (e.g. infrastructure-side issues outside our control) —
    the app should degrade gracefully, not crash, on a cloud dependency.
    """
    if MOTHERDUCK_TOKEN:
        try:
            return duckdb.connect(f"md:my_db?motherduck_token={MOTHERDUCK_TOKEN}", read_only=read_only)
        except Exception:
            pass
    return duckdb.connect(DUCKDB_PATH, read_only=read_only)


st.set_page_config(page_title="StreamPulse", page_icon="📦", layout="wide")
st.title("📦 StreamPulse")
st.caption("Near-real-time e-commerce order analytics + AI query agent")

try:
    _test_con = get_connection()
    _test_con.close()
    _db_available = True
except Exception:
    _db_available = False

if not _db_available:
    st.warning(
        "No database is currently reachable in this environment — neither "
        "MotherDuck nor a local pipeline database.\n\nThis is expected on "
        "the public deployment if MotherDuck's connection isn't available "
        "from this environment and the local pipeline hasn't synced data "
        "here."
    )
    st.stop()

tab_dashboard, tab_ai = st.tabs(["📊 Dashboard", "🤖 AI Query Agent"])

# ---------------------------------------------------------------------
# Dashboard tab
# ---------------------------------------------------------------------
with tab_dashboard:
    con = get_connection()
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

            st.dataframe(alerts.style.apply(highlight_severity, axis=1), width="stretch")
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

# ---------------------------------------------------------------------
# AI Query Agent tab
# ---------------------------------------------------------------------
with tab_ai:
    st.caption(
        "Ask a question in plain English. The generated SQL is always shown "
        "before results — only SELECT queries against `silver_orders` and "
        "`alerts` are allowed."
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    question = st.text_input(
        "Ask a question about your order data",
        placeholder="e.g. What were total sales by region?",
    )

    ask_clicked = st.button("Ask", type="primary")

    if ask_clicked and question.strip():
        with st.spinner("Generating SQL..."):
            try:
                result = execute_question(question)
                if UNABLE_TO_ANSWER_MARKER in result["sql"].lower():
                    st.session_state.chat_history.insert(0, {
                        "status": "unanswerable",
                        "question": question,
                        "sql": result["sql"],
                    })
                else:
                    st.session_state.chat_history.insert(0, {"status": "success", **result})
            except GuardrailViolation as e:
                st.session_state.chat_history.insert(0, {
                    "status": "blocked",
                    "question": question,
                    "reason": str(e),
                })
            except Exception as e:
                st.session_state.chat_history.insert(0, {
                    "status": "error",
                    "question": question,
                    "reason": str(e),
                })

    st.divider()

    if not st.session_state.chat_history:
        st.info("Ask a question above to get started.")

    for entry in st.session_state.chat_history:
        st.markdown(f"**Q: {entry['question']}**")

        if entry["status"] == "success":
            st.code(entry["sql"], language="sql")
            if entry["rows"]:
                st.dataframe(
                    [dict(zip(entry["columns"], row)) for row in entry["rows"]],
                    width="stretch",
                )
            else:
                st.info("Query ran successfully but returned no rows.")

        elif entry["status"] == "unanswerable":
            st.info(
                "🤷 I don't have the data to answer that. I can only answer "
                "questions using `silver_orders` (order data) and `alerts` "
                "(anomaly/data-quality alerts)."
            )
            with st.expander("Show generated SQL"):
                st.code(entry["sql"], language="sql")

        elif entry["status"] == "blocked":
            st.warning(f"🛑 Blocked by guardrails: {entry['reason']}")

        else:
            st.error(f"Something went wrong: {entry['reason']}")

        st.divider()
