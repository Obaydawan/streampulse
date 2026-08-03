# StreamPulse Architecture

## Current Status

**Phase:** 2.4 – First Public Deployment (Complete)

Producer, Redpanda, consumer, and a minimal Streamlit dashboard are all
verified working. The dashboard is publicly deployed.

**Live app:** https://streampulse.streamlit.app/

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
- Minimal Streamlit dashboard (row counts, recent orders, rejected events)
- Public deployment on Streamlit Community Cloud
- Documentation structure

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
  Streamlit Dashboard (local: shows live data)

## Current Pipeline (deployed)

  Streamlit Dashboard (Streamlit Cloud)
            │
            ▼
  No DuckDB access yet — shows "no database" message

The deployed app has no connection to the local pipeline's data yet.
This is architecturally expected at this phase, not a bug — the local
pipeline and the cloud deployment are currently separate. Connecting
them (e.g. via MotherDuck or a shared data store) is a planned later step.

---

## Planned Next Step

Phase 3 will add:

    DuckDB (bronze_orders)
            │
            ▼
       dbt (silver layer, tests)
            │
            ▼
       Alerts panel (anomaly/spike detection)
