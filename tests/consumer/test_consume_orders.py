"""
Unit tests for consumer/consume_orders.py

Uses a REAL temporary DuckDB file per test (not mocked) to catch actual
SQL bugs in schema creation and the idempotent insert logic — this is the
most important behavior in the whole consumer, so it gets real coverage.

Kafka/DLQ interaction is mocked since these are unit tests, not
integration tests against a live broker.
"""

import sys
import os
from unittest.mock import MagicMock

import duckdb
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from consumer.consume_orders import (
    validate_event,
    insert_event,
    init_db,
    handle_rejected_event,
)


VALID_EVENT = {
    "order_id": "test-order-001",
    "customer_id": "cust-001",
    "product_id": "prod-001",
    "product_name": "Test Widget",
    "region": "North America",
    "price": 19.99,
    "quantity": 2,
    "timestamp": "2026-08-01T12:00:00+00:00",
}


@pytest.fixture
def db_connection(tmp_path):
    """Real, temporary DuckDB file — created fresh and destroyed per test."""
    db_path = tmp_path / "test_orders.duckdb"
    con = duckdb.connect(str(db_path))
    init_db(con)
    yield con
    con.close()


# --- validate_event() tests ---

def test_validate_event_accepts_valid_event():
    assert validate_event(VALID_EVENT) is None


def test_validate_event_rejects_missing_field():
    bad_event = VALID_EVENT.copy()
    del bad_event["region"]
    reason = validate_event(bad_event)
    assert reason == "missing_field:region"


def test_validate_event_rejects_negative_price():
    bad_event = VALID_EVENT.copy()
    bad_event["price"] = -10
    assert validate_event(bad_event) == "invalid_price"


def test_validate_event_rejects_zero_quantity():
    bad_event = VALID_EVENT.copy()
    bad_event["quantity"] = 0
    assert validate_event(bad_event) == "invalid_quantity"


def test_validate_event_rejects_bad_timestamp():
    bad_event = VALID_EVENT.copy()
    bad_event["timestamp"] = "not-a-real-timestamp"
    assert validate_event(bad_event) == "invalid_timestamp"


def test_validate_event_rejects_empty_string_field():
    bad_event = VALID_EVENT.copy()
    bad_event["customer_id"] = ""
    reason = validate_event(bad_event)
    assert reason == "missing_field:customer_id"


# --- init_db() / insert_event() tests (real DuckDB) ---

def test_init_db_creates_expected_tables(db_connection):
    tables = {row[0] for row in db_connection.execute("SHOW TABLES").fetchall()}
    assert "bronze_orders" in tables
    assert "rejected_events" in tables


def test_insert_event_lands_correctly(db_connection):
    insert_event(db_connection, VALID_EVENT, partition=0, offset=1)
    result = db_connection.execute(
        "SELECT order_id, product_name, price FROM bronze_orders WHERE order_id = ?",
        [VALID_EVENT["order_id"]],
    ).fetchone()
    assert result is not None
    assert result[0] == VALID_EVENT["order_id"]
    assert result[1] == VALID_EVENT["product_name"]


def test_insert_event_is_idempotent_on_duplicate_order_id(db_connection):
    """The core guarantee: inserting the same order_id twice must not create a duplicate row."""
    insert_event(db_connection, VALID_EVENT, partition=0, offset=1)
    insert_event(db_connection, VALID_EVENT, partition=0, offset=2)  # simulated redelivery

    count = db_connection.execute(
        "SELECT COUNT(*) FROM bronze_orders WHERE order_id = ?",
        [VALID_EVENT["order_id"]],
    ).fetchone()[0]
    assert count == 1, "duplicate order_id must not create a second row"


def test_insert_event_different_order_ids_both_land(db_connection):
    event2 = VALID_EVENT.copy()
    event2["order_id"] = "test-order-002"

    insert_event(db_connection, VALID_EVENT, partition=0, offset=1)
    insert_event(db_connection, event2, partition=0, offset=2)

    count = db_connection.execute("SELECT COUNT(*) FROM bronze_orders").fetchone()[0]
    assert count == 2


# --- handle_rejected_event() tests (DLQ producer mocked) ---

def test_handle_rejected_event_logs_to_rejected_events_table(db_connection):
    mock_dlq_producer = MagicMock()
    raw_value = '{"bad": "event"}'

    handle_rejected_event(db_connection, mock_dlq_producer, raw_value, "invalid_price", 0, 5)

    result = db_connection.execute(
        "SELECT raw_value, reason FROM rejected_events WHERE source_offset = 5"
    ).fetchone()
    assert result is not None
    assert result[0] == raw_value
    assert result[1] == "invalid_price"


def test_handle_rejected_event_calls_dlq_producer(db_connection):
    mock_dlq_producer = MagicMock()
    raw_value = '{"bad": "event"}'

    handle_rejected_event(db_connection, mock_dlq_producer, raw_value, "invalid_price", 0, 5)

    mock_dlq_producer.produce.assert_called_once()
    mock_dlq_producer.poll.assert_called_once()
