"""
StreamPulse — dbt orchestration DAG.

Deliberately minimal, per project scope: orchestrates exactly what's
proven and needed — dbt run, then dbt test. Nothing more. Airflow was
introduced only after the underlying pipeline (producer, consumer, dbt
models) was already built, tested, and verified stable under load.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

DBT_PROJECT_DIR = "/home/obaydawan/projects/streampulse/dbt"

default_args = {
    "owner": "obaydawan",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="streampulse_dbt_pipeline",
    description="Run dbt models then test them — silver layer + alerts refresh",
    default_args=default_args,
    schedule=timedelta(minutes=15),
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["streampulse", "dbt"],
) as dag:

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt test --profiles-dir .",
    )

    dbt_run >> dbt_test
