FROM apache/airflow:2.10.5-python3.11
COPY requirements.txt /tmp/project-requirements.txt
RUN pip install --no-cache-dir "apache-airflow==2.10.5" -r /tmp/project-requirements.txt && pip check
COPY src /opt/project/src
COPY dbt/models /opt/project/dbt/models
COPY airflow/dags /opt/project/airflow/dags
COPY docker/postgres/init /opt/project/docker/postgres/init
ENV AIRFLOW__CORE__DAGS_FOLDER=/opt/project/airflow/dags GX_ANALYTICS_ENABLED=false
