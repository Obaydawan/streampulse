"""
Unit tests for ai_agent/guardrails.py — the safety-critical layer.

These tests assume the LLM could return ANYTHING, including malicious or
malformed SQL, and verify the guardrail catches it regardless of the
prompt's instructions. The prompt reduces bad attempts; these tests prove
the guardrail actually blocks them if the prompt fails.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from ai_agent.guardrails import validate_sql, GuardrailViolation


# --- Allowed queries should pass cleanly ---

def test_allows_simple_select_from_silver_orders():
    sql = "SELECT * FROM silver_orders"
    assert validate_sql(sql) == sql


def test_allows_simple_select_from_alerts():
    sql = "SELECT * FROM alerts"
    assert validate_sql(sql) == sql


def test_allows_select_with_where_and_group_by():
    sql = "SELECT region, SUM(order_total) FROM silver_orders GROUP BY region"
    assert validate_sql(sql) == sql


def test_allows_join_between_both_allowed_tables():
    sql = "SELECT a.alert_id, s.order_id FROM alerts a JOIN silver_orders s ON a.region = s.region"
    assert validate_sql(sql) == sql


def test_strips_trailing_semicolon():
    sql = "SELECT * FROM silver_orders;"
    assert validate_sql(sql) == "SELECT * FROM silver_orders"


# --- Disallowed tables must be blocked ---

def test_blocks_bronze_orders():
    with pytest.raises(GuardrailViolation, match="disallowed table"):
        validate_sql("SELECT * FROM bronze_orders")


def test_blocks_rejected_events():
    with pytest.raises(GuardrailViolation, match="disallowed table"):
        validate_sql("SELECT * FROM rejected_events")


def test_blocks_stg_orders():
    with pytest.raises(GuardrailViolation, match="disallowed table"):
        validate_sql("SELECT * FROM stg_orders")


def test_blocks_join_that_includes_one_disallowed_table():
    sql = "SELECT * FROM silver_orders s JOIN bronze_orders b ON s.order_id = b.order_id"
    with pytest.raises(GuardrailViolation, match="disallowed table"):
        validate_sql(sql)


# --- Non-SELECT statements must be blocked ---

def test_blocks_insert():
    with pytest.raises(GuardrailViolation):
        validate_sql("INSERT INTO silver_orders (order_id) VALUES ('x')")


def test_blocks_update():
    with pytest.raises(GuardrailViolation):
        validate_sql("UPDATE silver_orders SET order_total = 0")


def test_blocks_delete():
    with pytest.raises(GuardrailViolation):
        validate_sql("DELETE FROM silver_orders")


def test_blocks_drop_table():
    with pytest.raises(GuardrailViolation):
        validate_sql("DROP TABLE silver_orders")


def test_blocks_create_table():
    with pytest.raises(GuardrailViolation):
        validate_sql("CREATE TABLE evil (id INT)")


def test_blocks_alter_table():
    with pytest.raises(GuardrailViolation):
        validate_sql("ALTER TABLE silver_orders ADD COLUMN hacked INT")


def test_blocks_pragma():
    """
    PRAGMA statements aren't explicitly in forbidden_types, but they also
    aren't a valid exp.Select — confirming the isinstance(statement,
    exp.Select) check catches them as a side effect, not a gap.
    """
    with pytest.raises(GuardrailViolation):
        validate_sql("PRAGMA table_info('silver_orders')")


# --- Injection / bypass attempts ---

def test_blocks_multi_statement_injection():
    sql = "SELECT * FROM silver_orders; DROP TABLE silver_orders"
    with pytest.raises(GuardrailViolation, match="single SQL statement"):
        validate_sql(sql)


def test_blocks_empty_query():
    with pytest.raises(GuardrailViolation, match="Empty query"):
        validate_sql("")


def test_blocks_whitespace_only_query():
    with pytest.raises(GuardrailViolation, match="Empty query"):
        validate_sql("   ")


def test_blocks_unparseable_garbage():
    with pytest.raises(GuardrailViolation):
        validate_sql("this is not sql at all !!!")


def test_blocks_select_with_subquery_on_disallowed_table():
    sql = "SELECT * FROM silver_orders WHERE order_id IN (SELECT order_id FROM bronze_orders)"
    with pytest.raises(GuardrailViolation, match="disallowed table"):
        validate_sql(sql)
