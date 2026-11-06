FROM apache/airflow:2.10.5-python3.11
USER airflow
COPY --chown=airflow:root docker/airflow/requirements.txt /tmp/m1-airflow-requirements.txt
RUN pip install --no-cache-dir -r /tmp/m1-airflow-requirements.txt
RUN mkdir -p /home/airflow/.dbt
COPY --chown=airflow:root dbt/profiles.yml.example /home/airflow/.dbt/profiles.yml
