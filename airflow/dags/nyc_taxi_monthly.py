"""Manual end-to-end monthly NYC Taxi flow. No automatic scheduling in Week 2.

Trigger from Airflow UI with JSON: {"month": "2025-01"}
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

PROJECT_ROOT = "/opt/project"
MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def run_step(commands: list[list[str]], **context) -> None:
    month = context["params"]["month"]
    if not isinstance(month, str) or not MONTH_PATTERN.fullmatch(month):
        raise ValueError("month must match YYYY-MM")
    for command in commands:
        argv = [arg.replace("{month}", month) for arg in command]
        print("[M1] Executing:", argv, flush=True)
        subprocess.run(argv, cwd=PROJECT_ROOT, check=True, timeout=3600)


def verify_results(**context) -> None:
    import os
    from datetime import date

    import psycopg
    month = context["params"]["month"]
    if not isinstance(month, str) or not MONTH_PATTERN.fullmatch(month):
        raise ValueError("month must match YYYY-MM")
    year, mon = [int(p) for p in month.split("-")]
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('warehouse.fact_trip'), to_regclass('marts.agg_daily_demand')")
            fact, mart = cur.fetchone()
            if not fact or not mart:
                raise RuntimeError("dbt warehouse or marts models missing")
            cur.execute("SELECT COUNT(*) FROM staging.taxi_trips WHERE data_month = %s", (date(year, mon, 1),))
            staged = cur.fetchone()[0]
            if staged == 0:
                raise RuntimeError(f"No staged taxi rows for {month}")
            print(f"[M1] staging.taxi_trips rows for {month}: {staged}")


with DAG(
    dag_id="nyc_taxi_monthly_pipeline",
    description="M2 Bronze/Silver -> M3 staging/dbt -> M4-ready marts",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    params={"month": Param("2025-01", type="string", pattern=r"^\d{4}-(0[1-9]|1[0-2])$")},
    default_args={"owner": "m1", "retries": 1, "retry_delay": timedelta(minutes=2)},
    max_active_runs=1,
    tags=["nyc-taxi", "m1", "monthly"],
) as dag:
    taxi = PythonOperator(
        task_id="ingest_taxi_and_zones",
        python_callable=run_step,
        op_kwargs={"commands": [["python", "-m", "src.ingestion.taxi", "--month", "{month}"]]},
    )
    weather = PythonOperator(
        task_id="ingest_weather",
        python_callable=run_step,
        op_kwargs={"commands": [["python", "-m", "src.ingestion.weather", "--month", "{month}"]]},
    )
    silver = PythonOperator(
        task_id="validate_to_silver",
        python_callable=run_step,
        op_kwargs={"commands": [["python", "-m", "src.processing.validate", "--month", "{month}"]]},
    )
    staging = PythonOperator(
        task_id="load_postgres_staging",
        python_callable=run_step,
        op_kwargs={"commands": [["python", "-m", "src.warehouse.load_staging", "--month", "{month}"]]},
    )
    build = PythonOperator(
        task_id="build_dbt_warehouse_marts",
        python_callable=run_step,
        op_kwargs={"commands": [["dbt", "build", "--project-dir", "/opt/project/dbt", "--profiles-dir", "/home/airflow/.dbt"]]},
    )
    verify = PythonOperator(task_id="verify_output", python_callable=verify_results)
    [taxi, weather] >> silver >> staging >> build >> verify
