# StreamPulse

A real-time streaming data engineering project built to simulate an e-commerce order analytics platform.

## Project Goals

- Stream order events using Redpanda (Kafka API)
- Process events with Python consumers
- Build analytical models with dbt and DuckDB
- Orchestrate pipelines using Airflow
- Visualize live metrics with Streamlit
- Query data using an AI-powered SQL assistant (read-only)

## Tech Stack

- Python
- Redpanda
- DuckDB
- dbt
- Airflow
- Streamlit
- Docker
- Git & GitHub

## Project Status

🚧 Week 1 – Repository setup in progress.

## Live Deployment

🔗 **[streampulse.streamlit.app](https://streampulse.streamlit.app/)**

Note: the deployed dashboard currently shows a "no database found" message
by design — the streaming pipeline runs locally and hasn't been connected
to a shared cloud data store yet. This confirms the deployment pipeline
itself works correctly; connecting live data is planned for a later phase.
