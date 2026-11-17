"""Daily REE load for local runs, orchestrated by Airflow.

GitHub Actions rebuilds the whole history in a throwaway database every morning.
This DAG is the long-lived version: it keeps a persistent warehouse and only
re-reads the last 14 days, which is the window where REE still revises figures.

Backfill once from the UI with "Trigger DAG w/ config": {"start": "2023-01-01"}.
"""

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param

PROJECT = "/opt/pipeline"

with DAG(
    dag_id="ree_daily",
    description="REE daily generation: load, dbt build, export",
    schedule="17 8 * * *",
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Madrid"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    params={"start": Param(None, type=["null", "string"], format="date", description="Backfill from this day instead of the last 14 days")},
    tags=["ree", "dbt"],
) as dag:
    load = BashOperator(
        task_id="load",
        bash_command=(
            f"cd {PROJECT} && python -m ingest.load "
            "{% if params.start %}--start {{ params.start }}{% else %}--days 14{% endif %}"
        ),
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {PROJECT}/dbt && dbt build --profiles-dir .",
    )

    freshness = BashOperator(
        task_id="source_freshness",
        bash_command=f"cd {PROJECT}/dbt && dbt source freshness --profiles-dir .",
    )

    export = BashOperator(
        task_id="export",
        bash_command=f"cd {PROJECT} && python -m export.export_json --out site/data",
    )

    load >> dbt_build >> freshness >> export
