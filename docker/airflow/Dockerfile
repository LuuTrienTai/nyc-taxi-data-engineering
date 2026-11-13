FROM apache/airflow:2.10.5-python3.11
COPY requirements.txt /tmp/project-requirements.txt
RUN pip install --no-cache-dir "apache-airflow==2.10.5" -r /tmp/project-requirements.txt
ENV AIRFLOW__CORE__DAGS_FOLDER=/opt/project/airflow/dags
