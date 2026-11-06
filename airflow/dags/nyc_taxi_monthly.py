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
DEFAULT_MONTH = "2025-01"
MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def run_step(commands: list[list[str]], **context) -> None:
    month = context["params"]["month"]
    if not isinstance(month, str) or not MONTH_PATTERN.fullmatch(month):
        raise ValueError("month must match YYYY-MM")
    for command in commands:
        argv = [arg.replace("{month}", month) for arg in command]
        print("[M1] Executing:", argv, flush=True)
        subprocess.run(argv, cwd=PROJECT_ROOT, check=True, timeout=3600)


def audit_run(context, status: str) -> None:
    import psycopg

    from src.warehouse.load_staging import connection_kwargs

    run = context["dag_run"]
    month = (run.conf or {}).get("month", DEFAULT_MONTH)
    with psycopg.connect(**connection_kwargs()) as conn:
        conn.execute(
            """INSERT INTO audit.pipeline_runs
                   (dataset, data_period, airflow_run_id, started_at, finished_at, status, rows_loaded)
               VALUES ('nyc_taxi_monthly', %s, %s, %s, now(), %s,
                       CASE WHEN %s = 'success' THEN (
                           SELECT rows_loaded FROM audit.monthly_loads
                           WHERE dataset = 'taxi' AND data_month = to_date(%s, 'YYYY-MM')
                       ) END)
               ON CONFLICT (airflow_run_id) DO UPDATE
               SET finished_at = EXCLUDED.finished_at, status = EXCLUDED.status,
                   rows_loaded = EXCLUDED.rows_loaded
            """,
            (month, run.run_id, run.start_date, status, status, month),
        )


def audit_success(context) -> None:
    audit_run(context, "success")


def audit_failure(context) -> None:
    audit_run(context, "failed")


with DAG(
    dag_id="nyc_taxi_monthly_pipeline",
    description="M2 Bronze/Silver -> M3 staging/dbt -> M4-ready marts",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    params={"month": Param(DEFAULT_MONTH, type="string", pattern=r"^\d{4}-(0[1-9]|1[0-2])$")},
    default_args={"owner": "m1", "retries": 1, "retry_delay": timedelta(minutes=2)},
    max_active_runs=1,
    on_success_callback=audit_success,
    on_failure_callback=audit_failure,
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
        op_kwargs={"commands": [
            ["python", "-m", "src.processing.validate", "--month", "{month}"],
            ["python", "-m", "src.processing.verify_m2", "--month", "{month}"],
        ]},
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
    verify = PythonOperator(
        task_id="verify_output",
        python_callable=run_step,
        op_kwargs={"commands": [["python", "-m", "src.processing.validate_marts", "--month", "{month}"]]},
    )
    [taxi, weather] >> silver >> staging >> build >> verify
