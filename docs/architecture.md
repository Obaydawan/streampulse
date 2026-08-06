# StreamPulse Architecture

## Current Status

**Phase:** 5 – AI Analytics Assistant (Complete)

StreamPulse now implements a complete end-to-end streaming analytics pipeline
with a guardrailed AI SQL assistant. Real-time events are ingested through
Redpanda, transformed with dbt, orchestrated by Airflow, visualized in
Streamlit, and queried using Gemini-generated SQL protected by strict
guardrails.

**Live app:** https://streampulse.streamlit.app/

---

## Implemented

- Git repository, folder structure, environment configuration
- Docker Compose configuration for Redpanda (memory-capped)
- `orders` and `orders_dlq` Kafka topics
- Python producer generating synthetic e-commerce order events
- Python consumer ingesting valid events into DuckDB (`bronze_orders`)
- Invalid-event handling through DLQ and `rejected_events`
- dbt transformation pipeline:
  - `stg_orders`
  - `silver_orders`
  - `alerts`
- Airflow DAG orchestrating:
  - `dbt run`
  - `dbt test`
- Streamlit dashboard with:
  - Live metrics
  - Regional sales
  - Alerts panel
  - Recent orders
- Public Streamlit deployment
- Guardrailed AI SQL assistant powered by Gemini
- SQL execution engine with read-only enforcement
- SQL allowlist restricting access to:
  - `silver_orders`
  - `alerts`
- SQL validation preventing:
  - INSERT
  - UPDATE
  - DELETE
  - DROP
  - ALTER
  - CREATE
  - PRAGMA
  - Multiple statements
  - Access to Bronze or staging tables
- Tableless fallback responses for unsupported questions
- 45 automated pytest tests covering:
  - Producer
  - Consumer
  - AI SQL generator
  - SQL guardrails
  - Executor

---

## Current Pipeline (Local)

```
              Python Producer
                     │
                     ▼
          Redpanda Topic (orders)
                     │
                     ▼
             Python Consumer
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   bronze_orders          rejected_events
       │                       ▲
       │                       │
       ▼                 orders_dlq
      dbt
       │
       ▼
stg_orders
       │
       ▼
silver_orders
       │
       ▼
alerts
       │
       ├───────────────► Streamlit Dashboard
       │
       ▼
Guardrailed Gemini SQL Agent
       │
Generate SQL
       │
SQL Guardrails
       │
Execute SQL
       │
Return Results
```

---

## AI Query Flow

```
User Question
      │
      ▼
 Gemini SQL Generation
      │
      ▼
 SQL Guardrails
      │
      ├── Reject unsafe SQL
      │
      └── Allow safe SQL
             │
             ▼
      DuckDB Execution
             │
             ▼
      Results returned
```

---

## Current Deployment

### Local Environment

Runs the complete streaming system:

- Producer
- Consumer
- Redpanda
- DuckDB
- dbt
- Airflow
- Streamlit Dashboard
- Gemini SQL Assistant

### Streamlit Community Cloud

Currently hosts the dashboard UI.

The AI assistant can be deployed after configuring:

- `GEMINI_API_KEY` as a Streamlit secret

The dashboard currently does not connect to the local DuckDB database because
the streaming pipeline runs on the local development machine.

---

## Validation Status

✅ Producer validated

✅ Consumer validated

✅ dbt models validated

✅ dbt tests passing

✅ Airflow orchestration verified

✅ Dashboard operational

✅ Gemini integration verified

✅ SQL generation verified

✅ SQL execution verified

✅ SQL guardrails verified

✅ 45 automated tests passing

---

## Next Phase

**Phase 6 – Analytics Copilot**

The next phase adds an explanation layer that converts SQL query results into
clear business insights using Gemini while remaining grounded strictly in the
returned data and avoiding unsupported conclusions.
