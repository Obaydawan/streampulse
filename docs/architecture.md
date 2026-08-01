# StreamPulse Architecture

## Current Status

**Phase:** 1 – Redpanda + Producer (Complete)

Redpanda is running locally and the producer is verified end-to-end.

---

## Implemented

- Git repository
- Project folder structure
- Environment template (`.env.example`)
- Docker Compose configuration for Redpanda (running, memory-capped at 1G)
- `orders` topic created with 48h retention
- Python producer publishing synthetic order events to the `orders` topic
- Documentation structure

---

## Current Pipeline

    Python Producer
            │
            ▼
       Redpanda Topic (orders, 48h retention)

Verified end-to-end: producer publishes events with controlled bursts
(--max-events / --duration), graceful shutdown on Ctrl+C, and idempotent
delivery. Events confirmed landing in the topic via `rpk topic consume`.

---

## Planned Next Step

Phase 2 will add:

    Redpanda Topic
            │
            ▼
    Python Consumer (idempotent inserts, schema validation)
            │
            ▼
       DuckDB (bronze table)
            │
            ▼
    Streamlit (bare row-count page, first public deployment)
