"""
StreamPulse — Order Event Consumer

Reads order events from the Redpanda 'orders' topic, validates them, and
lands them into a local DuckDB bronze table with idempotent inserts keyed
on order_id.

Delivery guarantee: at-least-once. Kafka offsets are committed only AFTER
a successful DuckDB insert, so a crash mid-write causes re-delivery (not
data loss) — and re-delivery is made harmless by the ON CONFLICT DO
NOTHING insert, not by trying to achieve true exactly-once.

Run in short bursts, per hardware constraints — never run indefinitely.
Controlled by --max-events and/or --duration; whichever limit is hit
first stops the run. If neither is passed, defaults to 500 events.

Usage:
    python -m consumer.consume_orders --max-events 200
    python -m consumer.consume_orders --duration 60
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

import duckdb
from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv

from shared.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = os.getenv("TOPIC_NAME", "orders")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/orders.duckdb")

REQUIRED_FIELDS = [
    "order_id", "customer_id", "product_id", "product_name",
    "region", "price", "quantity", "timestamp",
]

_shutdown_requested = False


def _handle_sigint(signum, frame):
    global _shutdown_requested
    logger.warning("Shutdown signal received — finishing current event, then stopping")
    _shutdown_requested = True


def init_db(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS bronze_orders (
            order_id        VARCHAR PRIMARY KEY,
            customer_id     VARCHAR,
            product_id      VARCHAR,
            product_name    VARCHAR,
            region          VARCHAR,
            price           DOUBLE,
            quantity        INTEGER,
            event_timestamp TIMESTAMP,
            ingested_at     TIMESTAMP,
            source_partition INTEGER,
            source_offset    BIGINT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS rejected_events (
            raw_value    VARCHAR,
            reason       VARCHAR,
            rejected_at  TIMESTAMP,
            source_partition INTEGER,
            source_offset    BIGINT
        )
    """)
    logger.info(f"DuckDB ready at {DUCKDB_PATH} — bronze_orders + rejected_events tables confirmed")


def validate_event(event):
    for field in REQUIRED_FIELDS:
        if field not in event or event[field] in (None, ""):
            return f"missing_field:{field}"

    if not isinstance(event["price"], (int, float)) or event["price"] < 0:
        return "invalid_price"

    if not isinstance(event["quantity"], int) or event["quantity"] <= 0:
        return "invalid_quantity"

    try:
        datetime.fromisoformat(event["timestamp"])
    except (ValueError, TypeError):
        return "invalid_timestamp"

    return None


def insert_event(con, event, partition, offset):
    con.execute(
        """
        INSERT INTO bronze_orders (
            order_id, customer_id, product_id, product_name, region,
            price, quantity, event_timestamp, ingested_at,
            source_partition, source_offset
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (order_id) DO NOTHING
        """,
        [
            event["order_id"], event["customer_id"], event["product_id"],
            event["product_name"], event["region"], event["price"],
            event["quantity"], event["timestamp"],
            datetime.now(timezone.utc), partition, offset,
        ],
    )


def reject_event(con, raw_value, reason, partition, offset):
    con.execute(
        """
        INSERT INTO rejected_events (raw_value, reason, rejected_at, source_partition, source_offset)
        VALUES (?, ?, ?, ?, ?)
        """,
        [raw_value, reason, datetime.now(timezone.utc), partition, offset],
    )


def build_consumer():
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "streampulse-consumer",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
    return Consumer(conf)


def run(max_events, duration):
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    con = duckdb.connect(DUCKDB_PATH)
    init_db(con)

    consumer = build_consumer()
    consumer.subscribe([TOPIC_NAME])
    signal.signal(signal.SIGINT, _handle_sigint)

    start_time = time.monotonic()
    events_processed = 0
    events_rejected = 0

    logger.info(
        f"Starting consumer — topic='{TOPIC_NAME}' "
        f"max_events={max_events} duration={duration}"
    )

    try:
        while True:
            if _shutdown_requested:
                logger.info("Stopping due to shutdown signal")
                break

            if max_events is not None and events_processed >= max_events:
                logger.info(f"Reached max_events limit ({max_events}) — stopping")
                break

            if duration is not None and (time.monotonic() - start_time) >= duration:
                logger.info(f"Reached duration limit ({duration}s) — stopping")
                break

            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error(f"Consumer error: {msg.error()}")
                continue

            raw_value = msg.value().decode("utf-8")

            try:
                event = json.loads(raw_value)
            except json.JSONDecodeError:
                reject_event(con, raw_value, "invalid_json", msg.partition(), msg.offset())
                events_rejected += 1
                consumer.commit(msg)
                continue

            reason = validate_event(event)
            if reason is not None:
                logger.warning(f"Rejected event at offset {msg.offset()}: {reason}")
                reject_event(con, raw_value, reason, msg.partition(), msg.offset())
                events_rejected += 1
                consumer.commit(msg)
                continue

            insert_event(con, event, msg.partition(), msg.offset())
            consumer.commit(msg)
            events_processed += 1

            logger.info(f"Landed order_id={event['order_id']} (offset {msg.offset()})")

    finally:
        consumer.close()
        con.close()
        logger.info(
            f"Consumer stopped — {events_processed} landed, {events_rejected} rejected"
        )

    return events_processed, events_rejected


def parse_args():
    parser = argparse.ArgumentParser(description="StreamPulse order event consumer")
    parser.add_argument("--max-events", type=int, default=None, help="Stop after processing this many events")
    parser.add_argument("--duration", type=int, default=None, help="Stop after this many seconds")
    args = parser.parse_args()

    if args.max_events is None and args.duration is None:
        logger.warning("No --max-events or --duration provided — defaulting to 500 events")
        args.max_events = 500

    return args


if __name__ == "__main__":
    args = parse_args()
    landed, rejected = run(max_events=args.max_events, duration=args.duration)
    logger.info(f"Consumer run complete — {landed} landed, {rejected} rejected")
    sys.exit(0)
