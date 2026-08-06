"""
StreamPulse — AI Query Agent chat interface (Phase 5).

Natural language question -> Gemini generates SQL -> guardrails validate
-> SQL shown to the user -> DuckDB executes -> results shown.

The generated SQL is always displayed before/alongside execution, per the
project's guardrail design — nothing runs silently.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from ai_agent.executor import execute_question
from ai_agent.guardrails import GuardrailViolation

UNABLE_TO_ANSWER_MARKER = "unable to answer using available data"

st.set_page_config(page_title="StreamPulse AI Query", page_icon="🤖", layout="wide")
st.title("🤖 StreamPulse AI Query Agent")
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

col1, col2 = st.columns([1, 5])
with col1:
    ask_clicked = st.button("Ask", type="primary")

if ask_clicked and question.strip():
    with st.spinner("Generating SQL..."):
        try:
            result = execute_question(question)
            # The model's designed fallback for unanswerable questions is
            # a tableless SELECT literal — recognize it as a graceful
            # decline, not a successful data result.
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
