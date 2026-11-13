"""Manual monthly backfill: explicit month avoids processing unpublished TLC months."""
from datetime import datetime,timedelta
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

def ingest(month):
    from src.config import ensure_directories
    from src.ingestion.taxi import validate_month_arg,ingest_zones,ingest_taxi_month
    from src.ingestion.weather import ingest_weather_month
    validate_month_arg(month);ensure_directories()
    ingest_zones();ingest_taxi_month(month);ingest_weather_month(month)
def transform(month):
    from src.pipeline import build_gold
    build_gold(month)
def verify(month):
    from src.verify import verify_month
    verify_month(month)
with DAG('nyc_taxi_monthly_pipeline',start_date=datetime(2025,1,1),schedule=None,
         catchup=False,max_active_runs=1,
         params={'month':Param('2025-01',type='string',pattern=r'^\d{4}-(0[1-9]|1[0-2])$')},
         default_args={'owner':'team','retries':2,'retry_delay':timedelta(minutes=2)},
         tags=['bronze','transient-silver','gold']) as dag:
    a=PythonOperator(task_id='ingest_bronze',python_callable=ingest,op_kwargs={'month':'{{ params.month }}'})
    b=PythonOperator(task_id='silver_in_memory_to_gold',python_callable=transform,op_kwargs={'month':'{{ params.month }}'})
    c=PythonOperator(task_id='verify_gold',python_callable=verify,op_kwargs={'month':'{{ params.month }}'})
    a >> b >> c
