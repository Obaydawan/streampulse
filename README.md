# StreamPulse

Near-real-time order analytics pipeline with a natural-language query agent. Events flow through a Kafka-compatible stream into a warehouse, get transformed with dbt, and surface on a live dashboard — alongside an AI agent that answers questions about the data in plain English, with SQL you can see before it runs.

**Live app:** [streampulse.streamlit.app](https://streampulse.streamlit.app/)

## What Project does

- Streams synthetic e-commerce order events through Redpanda
- Lands them in DuckDB with schema validation and idempotent writes — duplicate deliveries never produce duplicate rows
- Transforms raw events into analytics-ready tables with dbt, fully tested
- Detects anomalies: high-value orders, regional order spikes, data quality failures
- Orchestrates the pipeline with Airflow
- Answers natural-language questions about the data through Gemini, with the generated SQL restricted to read-only queries against an explicit table allowlist
- Explains query results in plain English, grounded strictly in the returned data

Micro-batch, not true streaming SQL — the consumer writes continuously, dbt transforms on a schedule. Worth saying directly rather than letting "real-time" do more work than it should.

## Architecture

```
Producer → Redpanda (48h retention) → Consumer
                                          |
                          -----------------------------
                          |                            |
                          v                            v
                    bronze_orders                orders_dlq +
                    (valid events)               rejected_events
                          |                       (invalid events)
                          v
                         dbt
                          |
          stg_orders -> silver_orders -> alerts
                          |
                          v
                    Streamlit
              -----------------------
              |                     |
              v                     v
          Dashboard            AI Query Agent
                            (Gemini -> guardrails ->
                             DuckDB -> explanation)
```

Airflow orchestrates `dbt run` then `dbt test` on a schedule. It was added last, after the pipeline was already proven stable — scheduling untested code just makes failures harder to debug.

Local development runs against a local DuckDB file. The deployed dashboard reads from MotherDuck, synced from that same pipeline output, since a public deployment has no access to a developer's machine.

## Stack

SQL,Redpanda, Python, DuckDB, MotherDuck, dbt, Airflow, Streamlit, Gemini, sqlglot, pytest, Docker

## The AI agent

Three things make this safe to expose publicly rather than just a demo trick:

Every generated query is parsed, not pattern-matched. sqlglot builds a real syntax tree from the model's output and checks it — SELECT-only, and only against silver_orders and alerts. A disallowed table hidden inside a join or a subquery gets caught the same as one written plainly.

Nothing runs silently. The SQL is shown to the user alongside the results, every time.

Results get explained, not embellished. A second model call summarizes what the data shows, explicitly barred from inventing a "why" the data doesn't support. "Europe had the highest sales" is fine. "Europe had the highest sales due to strong regional demand" is not — nothing in the results says that.

If a question falls outside what the two allowed tables can answer, the agent says so directly instead of guessing.

## Testing

50 automated tests. The ones worth mentioning specifically:

A test that proves the consumer's idempotency guarantee directly — the same order processed twice produces exactly one row.

21 tests attacking the SQL guardrails: disallowed tables, every forbidden operation, multi-statement injection, malformed input.

AI agent tests run against mocked model clients, so the suite stays fast and doesn't burn API quota on every run.

A three-minute sustained load test, producer and consumer running concurrently, held steady at ~230MB memory and ~1.15 events per second, with zero data loss.

## Security and limitations

Read-only database connections for the AI agent, syntax-tree SQL validation, an explicit table allowlist, and secrets kept out of source control entirely — environment variables locally, platform secrets in deployment.

What it isn't: multi-user, authenticated, or built for high concurrency. Chat history lives in the browser session and disappears on refresh. The public deployment is a synced snapshot, not a live feed from the running pipeline.

## Running it locally

```
git clone https://github.com/Obaydawan/streampulse.git
cd streampulse
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

docker-compose up -d
python -m producer.produce_orders --max-events 50
python -m consumer.consume_orders --max-events 50

cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir . && cd ..
streamlit run streamlit_app/app.py
```

Needs a .env file (see .env.example) with GEMINI_API_KEY. MOTHERDUCK_TOKEN is optional, for cloud sync.

## Engineering journal

PROJECT_JOURNAL.md covers the real debugging history — including a multi-day authentication issue that turned out to be a DuckDB/MotherDuck version mismatch, a Streamlit Cloud deployment that silently hung on a Python version mismatch, and the usual dbt and Airflow configuration friction that doesn't make it into most write-ups.
