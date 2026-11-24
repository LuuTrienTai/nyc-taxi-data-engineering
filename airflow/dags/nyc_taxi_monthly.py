"""Monthly scheduled processing and explicit manual backfills."""
import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

from src.config import DATA_DIR


def ingest(month, replay_bronze):
    from src.pipeline import ingest_month

    if not replay_bronze:
        ingest_month(month)


def transform(month):
    from src.pipeline import build_gold

    build_gold(month)


def verify(month):
    from src.verify import verify_month

    verify_month(month)


month = (
    "{{ params.month or data_interval_end.in_timezone('America/New_York').subtract(months="
    + str(int(os.environ.get('TAXI_MONTH_LAG', '3')))
    + ").format('YYYY-MM') }}"
)

with DAG(
    'nyc_taxi_monthly_pipeline',
    start_date=pendulum.datetime(2025, 1, 1, tz='America/New_York'),
    schedule=None if DATA_DIR.name == 'demo' else '0 6 15 * *',
    catchup=False,
    max_active_runs=1,
    render_template_as_native_obj=True,
    params={
        'month': Param(None, type=['null', 'string'], pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
        'replay_bronze': Param(DATA_DIR.name == 'demo', type='boolean'),
    },
    default_args={'owner': 'team', 'retries': 2, 'retry_delay': timedelta(minutes=5)},
    tags=['bronze', 'silver', 'gold', 'quarantine'],
) as dag:
    bronze = PythonOperator(task_id='ingest_bronze', python_callable=ingest,
                            op_kwargs={'month': month, 'replay_bronze': '{{ params.replay_bronze }}'})
    silver_gold = PythonOperator(task_id='silver_transform_and_load_gold', python_callable=transform,
                                 op_kwargs={'month': month})
    checked = PythonOperator(task_id='verify_gold', python_callable=verify, op_kwargs={'month': month})
    bronze >> silver_gold >> checked
