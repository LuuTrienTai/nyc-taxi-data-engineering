import os
import psycopg
from psycopg import sql
from src.config import connection_kwargs
with psycopg.connect(**connection_kwargs(),autocommit=True) as c:
    if not c.execute("SELECT 1 FROM pg_database WHERE datname='airflow_meta'").fetchone():
        c.execute('CREATE DATABASE airflow_meta')
    if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='metabase_reader'").fetchone():
        c.execute('CREATE ROLE metabase_reader LOGIN')
    c.execute(sql.SQL('ALTER ROLE metabase_reader PASSWORD {}').format(sql.Literal(os.environ['METABASE_READER_PASSWORD'])))
    c.execute('GRANT USAGE ON SCHEMA gold TO metabase_reader')
    c.execute('GRANT SELECT ON ALL TABLES IN SCHEMA gold TO metabase_reader')
    c.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO metabase_reader')
    print('Airflow metadata DB and read-only Metabase role ready')
