# StreamPulse Architecture

## Current Status

**Phase:** 2.1 – Consumer + DLQ (Complete)

Producer, Redpanda, and consumer are all verified working end-to-end,
including the dead-letter-queue rejection path.

---

## Implemented

- Git repository
- Project folder structure
- Environment template (`.env.example`)
- Docker Compose configuration for Redpanda (running, memory-capped at 1G)
- `orders` topic (48h retention) and `orders_dlq` topic (48h retention)
- Python producer publishing synthetic order events
- Python consumer landing valid events into DuckDB (`bronze_orders`), idempotent on `order_id`
- Invalid-event handling: schema validation, routed to both `orders_dlq` (with reason header) and DuckDB `rejected_events` table
- Documentation structure

---

## Current Pipeline

    Python Producer
            │
            ▼
       Redpanda Topic (orders, 48h retention)
            │
            ▼
       Python Consumer
            │
      ┌─────┴─────┐
      ▼           ▼
  bronze_orders   orders_dlq (invalid events)
  (DuckDB)        + rejected_events (DuckDB)

Verified: 34+ valid events landed correctly; a deliberately invalid event
(negative price) was correctly caught, routed to the DLQ topic with a
reason header, and logged in DuckDB for inspection.

---

## Planned Next Step

Phase 2.4 will add:

    DuckDB (bronze_orders)
            │
            ▼
    Streamlit (bare row-count page, first public deployment)
