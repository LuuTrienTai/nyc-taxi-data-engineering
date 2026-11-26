FROM python:3.11-slim
WORKDIR /opt/project
COPY requirements.txt .
COPY dbt/requirements.txt dbt-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r dbt-requirements.txt
COPY . .
RUN mkdir -p /opt/project/data && chmod 2775 /opt/project/data
ENV PYTHONPATH=/opt/project PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.pipeline", "--help"]
