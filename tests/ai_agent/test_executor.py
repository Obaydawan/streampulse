"""
Unit tests for ai_agent/executor.py using a mocked SQLGenerator — no real
Gemini API calls, so these tests run free and fast, and don't depend on
network access or API quota.
"""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from ai_agent.executor import execute_question
from ai_agent.guardrails import GuardrailViolation


def make_mock_generator(sql_to_return: str):
    mock_gen = MagicMock()
    mock_gen.generate_sql.return_value = sql_to_return
    return mock_gen


def test_execute_question_returns_expected_shape():
    mock_gen = make_mock_generator("SELECT COUNT(*) AS total FROM silver_orders")
    result = execute_question("How many orders?", generator=mock_gen)

    assert result["question"] == "How many orders?"
    assert "SELECT" in result["sql"]
    assert "total" in result["columns"]
    assert len(result["rows"]) == 1


def test_execute_question_calls_generator_with_the_question():
    mock_gen = make_mock_generator("SELECT * FROM alerts")
    execute_question("Show me alerts", generator=mock_gen)
    mock_gen.generate_sql.assert_called_once_with("Show me alerts")


def test_execute_question_blocks_disallowed_table_before_running():
    """
    Even if Gemini misbehaves and returns a query against a disallowed
    table, the executor must raise GuardrailViolation and never reach
    the database.
    """
    mock_gen = make_mock_generator("SELECT * FROM bronze_orders")
    with pytest.raises(GuardrailViolation, match="disallowed table"):
        execute_question("Show me raw orders", generator=mock_gen)


def test_execute_question_blocks_non_select():
    mock_gen = make_mock_generator("DROP TABLE silver_orders")
    with pytest.raises(GuardrailViolation):
        execute_question("Delete everything", generator=mock_gen)
