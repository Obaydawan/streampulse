"""
Unit tests for producer/produce_orders.py

Focus: event generation correctness and CLI argument defaults.
Does NOT require a live Redpanda broker.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from producer.produce_orders import generate_order_event, PRODUCT_CATALOG, REGIONS


def test_generate_order_event_has_all_required_fields():
    event = generate_order_event()
    required_fields = [
        "order_id", "customer_id", "product_id", "product_name",
        "region", "price", "quantity", "timestamp",
    ]
    for field in required_fields:
        assert field in event, f"missing field: {field}"


def test_generate_order_event_price_is_positive():
    event = generate_order_event()
    assert event["price"] > 0


def test_generate_order_event_quantity_in_valid_range():
    event = generate_order_event()
    assert 1 <= event["quantity"] <= 5


def test_generate_order_event_region_is_from_known_list():
    event = generate_order_event()
    assert event["region"] in REGIONS


def test_generate_order_event_product_is_from_catalog():
    event = generate_order_event()
    known_products = [name for name, _ in PRODUCT_CATALOG]
    assert event["product_name"] in known_products


def test_generate_order_event_order_id_is_unique_across_calls():
    event1 = generate_order_event()
    event2 = generate_order_event()
    assert event1["order_id"] != event2["order_id"]


def test_generate_order_event_product_id_is_deterministic_per_product():
    """Same product name should always map to the same product_id (uuid5)."""
    matching_events = []
    for _ in range(50):
        event = generate_order_event()
        if event["product_name"] == PRODUCT_CATALOG[0][0]:
            matching_events.append(event["product_id"])
    if len(matching_events) >= 2:
        assert len(set(matching_events)) == 1, "same product should always get the same product_id"
