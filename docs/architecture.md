# StreamPulse Architecture

## Current Status

**Phase:** 4 – Testing, Stabilization, Orchestration (Complete)

Full local pipeline verified end-to-end, load-tested, and now orchestrated
by Airflow. This is a legitimate standalone milestone even before the AI
layer is added.

**Live app:** https://streampulse.streamlit.app/

---

## Implemented

- Git repository, folder structure, environment template
- Docker Compose configuration for Redpanda (running, memory-capped at 1G)
- `orders` topic (48h retention) and `orders_dlq` topic (48h retention)
- Python producer publishing synthetic order events
- Python consumer landing valid events into DuckDB (`bronze_orders`), idempotent on `order_id`
- Invalid-event handling: `orders_dlq` topic + DuckDB `rejected_events` table
- dbt project: `stg_orders`, `silver_orders`, `alerts` (all tested)
- Streamlit dashboard: metrics, color-coded Alerts panel, recent orders
- Public deployment on Streamlit Community Cloud
- 19 pytest unit tests (producer + consumer), idempotency formally verified
- Sustained load test: stable memory (~230MiB), ~1.15 events/sec throughput,
  at-least-once delivery proven correct under real timing edge cases
- Airflow (standalone-appropriate config) orchestrating dbt_run >> dbt_test

---

## Current Pipeline (local)

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
      │
      ▼
     dbt (orchestrated by Airflow: dbt_run >> dbt_test)
      │
  stg_orders → silver_orders → alerts
      │
      ▼
Streamlit Dashboard (local: full live view — metrics, alerts, orders)

## Current Pipeline (deployed)

  Streamlit Dashboard (Streamlit Cloud)
            │
            ▼
  No DuckDB access yet — shows "no database" message

---

## Planned Next Step

Phase 5 will add:
    Guardrailed AI query agent — SELECT-only, table allowlist,
    SQL shown before execution, plain-English explanation of results
