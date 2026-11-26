"""Provision the local dashboard reader and Airflow's metadata database."""
import os

import psycopg
from psycopg import sql

from src.config import connection_kwargs, ensure_directories


def login(conn, role, password):
    if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
        conn.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier(role)))
    conn.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role), sql.Literal(password)))


def setup():
    ensure_directories()
    with psycopg.connect(**connection_kwargs(), autocommit=True) as conn:
        conn.execute('SELECT pg_advisory_lock(381079)')
        login(conn, 'taxi_web_reader', os.environ['WEB_READER_PASSWORD'])
        conn.execute('ALTER ROLE taxi_web_reader SET default_transaction_read_only = on')
        conn.execute('GRANT USAGE ON SCHEMA gold, audit, quarantine TO taxi_web_reader')
        conn.execute('GRANT SELECT ON ALL TABLES IN SCHEMA gold TO taxi_web_reader')
        conn.execute("""
            GRANT SELECT (run_id, data_month, source_kind, status, started_at, finished_at,
                rows_read, rows_loaded, rows_rejected, bronze_files, preview)
            ON audit.pipeline_runs TO taxi_web_reader
        """)
        conn.execute('GRANT SELECT ON quarantine.rejected_trip, quarantine.rejection_summary TO taxi_web_reader')
        login(conn, 'taxi_airflow', os.environ['AIRFLOW_DB_PASSWORD'])
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname='airflow_meta'").fetchone():
            conn.execute('CREATE DATABASE airflow_meta OWNER taxi_airflow')
        conn.execute('REVOKE CONNECT ON DATABASE airflow_meta FROM PUBLIC')


if __name__ == '__main__':
    setup()
