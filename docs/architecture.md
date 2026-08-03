# StreamPulse Architecture

## Current Status

**Phase:** 3.2 – dbt Silver Layer + Alerts Panel (Complete)

Full local pipeline verified end-to-end, including anomaly/data-quality
alerting surfaced in the dashboard.

**Live app:** https://streampulse.streamlit.app/

---

## Implemented

- Git repository, folder structure, environment template
- Docker Compose configuration for Redpanda (running, memory-capped at 1G)
- `orders` topic (48h retention) and `orders_dlq` topic (48h retention)
- Python producer publishing synthetic order events
- Python consumer landing valid events into DuckDB (`bronze_orders`), idempotent on `order_id`
- Invalid-event handling: `orders_dlq` topic + DuckDB `rejected_events` table
- dbt project: `stg_orders` (staging view), `silver_orders` (materialized table, derived `order_total`)
- dbt `alerts` model: unified data_quality + high_value_order + region_spike detection, all fields tested
- Streamlit dashboard: metrics, color-coded Alerts panel, recent orders from silver layer
- Public deployment on Streamlit Community Cloud

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
     dbt
      │
  ┌───┴────┐
  ▼        ▼
stg_orders  →  silver_orders  →  alerts
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

Phase 4 will add:
    - pytest coverage for producer/consumer
    - Full pipeline stabilization testing under sustained load
    - Airflow orchestration for scheduled dbt runs
