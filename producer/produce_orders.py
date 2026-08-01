"""
StreamPulse — Order Event Producer

Publishes synthetic e-commerce order events to the Redpanda 'orders' topic.

Run in short bursts, per hardware constraints (8GB RAM, dual-core) — never
run indefinitely. Controlled by --max-events and/or --duration; whichever
limit is hit first stops the run. If neither is passed, defaults to 500
events so a bare `python produce_orders.py` can never run forever.

Usage:
    python produce_orders.py --max-events 200
    python produce_orders.py --duration 60
    python produce_orders.py --max-events 1000 --duration 120
"""

import argparse
import json
import os
import random
import signal
import sys
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer
from dotenv import load_dotenv
from faker import Faker

from shared.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)
fake = Faker()

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = os.getenv("TOPIC_NAME", "orders")

REGIONS = ["North America", "Europe", "Asia Pacific", "South America", "Middle East"]
PRODUCT_CATALOG = [
    ("Wireless Mouse", 19.99),
    ("Mechanical Keyboard", 89.99),
    ("USB-C Hub", 34.99),
    ("Laptop Stand", 45.00),
    ("Noise Cancelling Headphones", 129.99),
    ("Webcam 1080p", 39.99),
    ("Desk Lamp", 24.99),
    ("Portable SSD 1TB", 79.99),
    ("Ergonomic Chair Cushion", 29.99),
    ("Bluetooth Speaker", 54.99),
]

_shutdown_requested = False


def _handle_sigint(signum, frame):
    global _shutdown_requested
    logger.warning("Shutdown signal received — finishing current event, then stopping")
    _shutdown_requested = True


def generate_order_event() -> dict:
    """Build a single synthetic order event."""
    product_name, unit_price = random.choice(PRODUCT_CATALOG)
    quantity = random.randint(1, 5)

    return {
        "order_id": str(uuid.uuid4()),
        "customer_id": fake.uuid4(),
        "product_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, product_name)),
        "product_name": product_name,
        "region": random.choice(REGIONS),
        "price": round(unit_price, 2),
        "quantity": quantity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def delivery_report(err, msg):
    """Called once per produced message to confirm delivery or log failure."""
    if err is not None:
        logger.error(f"Delivery failed for order_id={msg.key()}: {err}")
    else:
        logger.info(
            f"Delivered order_id={msg.key().decode('utf-8')} "
            f"to {msg.topic()} [partition {msg.partition()}]"
        )


def build_producer() -> Producer:
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "client.id": "streampulse-producer",
        "acks": "all",
        "enable.idempotence": True,
        "retries": 5,
    }
    return Producer(conf)


def run(max_events, duration):
    producer = build_producer()
    signal.signal(signal.SIGINT, _handle_sigint)

    start_time = time.monotonic()
    events_sent = 0

    logger.info(
        f"Starting producer — topic='{TOPIC_NAME}' "
        f"max_events={max_events} duration={duration}s"
    )

    try:
        while True:
            if _shutdown_requested:
                logger.info("Stopping due to shutdown signal")
                break

            if max_events is not None and events_sent >= max_events:
                logger.info(f"Reached max_events limit ({max_events}) — stopping")
                break

            if duration is not None and (time.monotonic() - start_time) >= duration:
                logger.info(f"Reached duration limit ({duration}s) — stopping")
                break

            event = generate_order_event()

            try:
                producer.produce(
                    topic=TOPIC_NAME,
                    key=event["order_id"].encode("utf-8"),
                    value=json.dumps(event).encode("utf-8"),
                    callback=delivery_report,
                )
                producer.poll(0)
                events_sent += 1
            except BufferError:
                logger.warning("Producer queue full — flushing before continuing")
                producer.flush(5)

            time.sleep(random.uniform(0.2, 1.5))

    finally:
        logger.info(f"Flushing producer — {events_sent} events sent this run")
        remaining = producer.flush(10)
        if remaining > 0:
            logger.warning(f"{remaining} messages were not delivered before flush timeout")
        else:
            logger.info("All messages flushed successfully")

    return events_sent


def parse_args():
    parser = argparse.ArgumentParser(description="StreamPulse order event producer")
    parser.add_argument("--max-events", type=int, default=None, help="Stop after producing this many events")
    parser.add_argument("--duration", type=int, default=None, help="Stop after this many seconds")
    args = parser.parse_args()

    if args.max_events is None and args.duration is None:
        logger.warning("No --max-events or --duration provided — defaulting to 500 events")
        args.max_events = 500

    return args


if __name__ == "__main__":
    args = parse_args()
    total = run(max_events=args.max_events, duration=args.duration)
    logger.info(f"Producer run complete — {total} events sent")
    sys.exit(0)
