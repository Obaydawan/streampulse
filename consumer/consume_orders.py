"""
StreamPulse — Order Event Consumer

Reads order events from the Redpanda 'orders' topic, validates them, and
lands them into a local DuckDB bronze table with idempotent inserts keyed
on order_id. Invalid events are sent to the orders_dlq topic AND logged
into a DuckDB rejected_events table for easy querying later.

Delivery guarantee: at-least-once. Kafka offsets are committed only AFTER
a successful DuckDB insert, so a crash mid-write causes re-delivery, not
data loss — made harmless by ON CONFLICT DO NOTHING.

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
from confluent_kafka import Consumer, Producer, KafkaError
from dotenv import load_dotenv

from shared.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = os.getenv("TOPIC_NAME", "orders")
DLQ_TOPIC_NAME = os.getenv("DLQ_TOPIC_NAME", "orders_dlq")
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


def dlq_delivery_report(err, msg):
    if err is not None:
        logger.error(f"Failed to deliver to DLQ: {err}")


def handle_rejected_event(con, dlq_producer, raw_value, reason, partition, offset):
    """Single place for rejection handling: DLQ publish + DuckDB log + warning."""
    dlq_producer.produce(
        topic=DLQ_TOPIC_NAME,
        value=raw_value.encode("utf-8"),
        headers={"reason": reason.encode("utf-8")},
        callback=dlq_delivery_report,
    )
    dlq_producer.poll(0)

    con.execute(
        """
        INSERT INTO rejected_events (raw_value, reason, rejected_at, source_partition, source_offset)
        VALUES (?, ?, ?, ?, ?)
        """,
        [raw_value, reason, datetime.now(timezone.utc), partition, offset],
    )

    logger.warning(f"Rejected event at offset {offset}: {reason}")


def build_consumer():
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "streampulse-consumer",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
    return Consumer(conf)


def build_dlq_producer():
    return Producer({"bootstrap.servers": BOOTSTRAP_SERVERS, "client.id": "streampulse-dlq-producer"})


def run(max_events, duration):
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    con = duckdb.connect(DUCKDB_PATH)
    init_db(con)

    consumer = build_consumer()
    dlq_producer = build_dlq_producer()
    consumer.subscribe([TOPIC_NAME])
    signal.signal(signal.SIGINT, _handle_sigint)

    start_time = time.monotonic()
    events_processed = 0
    events_rejected = 0

    logger.info(
        f"Starting consumer — topic='{TOPIC_NAME}' dlq='{DLQ_TOPIC_NAME}' "
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
                handle_rejected_event(con, dlq_producer, raw_value, "invalid_json", msg.partition(), msg.offset())
                events_rejected += 1
                consumer.commit(msg)
                continue

            reason = validate_event(event)
            if reason is not None:
                handle_rejected_event(con, dlq_producer, raw_value, reason, msg.partition(), msg.offset())
                events_rejected += 1
                consumer.commit(msg)
                continue

            insert_event(con, event, msg.partition(), msg.offset())
            consumer.commit(msg)
            events_processed += 1

            logger.info(f"Landed order_id={event['order_id']} (offset {msg.offset()})")

    finally:
        dlq_producer.flush(5)
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
