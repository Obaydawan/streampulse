"""
Unit tests for ai_agent/explain.py using a mocked GeminiClient — no real
API calls, consistent with the rest of the test suite.
"""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_agent.explain import explain_results, MAX_ROWS_IN_PROMPT


def make_mock_client(response_text: str):
    mock_client = MagicMock()
    mock_client.generate.return_value = response_text
    return mock_client


def test_explain_results_returns_client_response():
    mock_client = make_mock_client("Europe had the highest total sales at $12,450.")
    result = explain_results(
        question="Total sales by region?",
        sql="SELECT region, SUM(order_total) FROM silver_orders GROUP BY region",
        columns=["region", "total"],
        rows=[("Europe", 12450), ("North America", 9800)],
        client=mock_client,
    )
    assert result == "Europe had the highest total sales at $12,450."


def test_explain_results_handles_empty_rows_without_calling_client():
    """
    Empty results should short-circuit with a plain message — no need to
    burn an API call explaining that there's nothing to explain.
    """
    mock_client = make_mock_client("should not be used")
    result = explain_results(
        question="Show orders from Mars",
        sql="SELECT * FROM silver_orders WHERE region = 'Mars'",
        columns=["order_id"],
        rows=[],
        client=mock_client,
    )
    assert "no results" in result.lower()
    mock_client.generate.assert_not_called()


def test_explain_results_passes_question_and_data_to_client():
    mock_client = make_mock_client("Some summary.")
    explain_results(
        question="How many orders?",
        sql="SELECT COUNT(*) AS total FROM silver_orders",
        columns=["total"],
        rows=[(242,)],
        client=mock_client,
    )
    call_args = mock_client.generate.call_args[0][0]
    assert "How many orders?" in call_args
    assert "total" in call_args
    assert "242" in call_args


def test_explain_results_truncates_large_row_sets():
    mock_client = make_mock_client("Summary of many rows.")
    many_rows = [(f"order_{i}", i * 10) for i in range(100)]
    explain_results(
        question="Show all orders",
        sql="SELECT order_id, total FROM silver_orders",
        columns=["order_id", "total"],
        rows=many_rows,
        client=mock_client,
    )
    call_args = mock_client.generate.call_args[0][0]
    assert f"first {MAX_ROWS_IN_PROMPT} of 100 total rows" in call_args
    # Only the first MAX_ROWS_IN_PROMPT rows' data should appear, not row 99
    assert "order_99" not in call_args


def test_explain_results_strips_whitespace_from_response():
    mock_client = make_mock_client("  Padded response.  \n")
    result = explain_results(
        question="q", sql="SELECT 1", columns=["x"], rows=[(1,)], client=mock_client
    )
    assert result == "Padded response."
