# M1 — Week 1 + Week 2: Infrastructure and orchestration

## Scope
- **Week 1:** repository structure, Docker Compose (PostgreSQL 16 + Metabase), `.env` configuration, schemas and a repeatable smoke test.
- **Week 2:** *optional* Docker Compose extension for Airflow, manual monthly DAG, task ordering, retries/logs, basic output checks.
- M1 does not own Bronze/Silver transforms (M2), staging/dbt models (M3), or dashboards (M4).

## Branch and file ownership
Work on `feature/m1-infra-orchestration`, branched from current `main`; do not commit generated credentials or data.
Only added files: `compose.airflow.yaml`, `docker/airflow/*`, `airflow/dags/*`, `scripts/m1_*`, `docs/M1_WEEK1_WEEK2.md`, and `tests/test_m1_structure.py`.
The pre-existing `compose.yaml` and `.env.example` from main are intentionally unchanged.

## Prerequisites
- Docker Desktop with Compose plugin installed, Python 3.11+ (local static tests), sufficient free storage for monthly taxi Parquet.
- Integrate **M2 Week 1** and **M3 Week 1 + Week 2** branches into a shared integration branch *before* running the complete DAG.
- Airflow + Metabase + PostgreSQL may exceed a 16GB host when coupled with a full taxi data load. Close unnecessary apps; start with a single month.
- `.env` values `POSTGRES_PASSWORD`, `AIRFLOW_SECRET_KEY`, `AIRFLOW_ADMIN_PASSWORD` must be changed from placeholders. For this local compose DSN, use URL-safe alphanumeric passwords (special URI characters require percent encoding). Keep Airflow localhost-only.

## Week 1 commands (from repo root)
```bash
cp .env.example .env  # if .env does not yet exist
# Edit .env: POSTGRES_PASSWORD is required and must not be a placeholder
# Add AIRFLOW_SECRET_KEY, AIRFLOW_ADMIN_USER, AIRFLOW_ADMIN_PASSWORD, AIRFLOW_PORT lines shown below.
docker compose config
docker compose up -d postgres metabase
docker compose ps
python3 scripts/m1_smoke_test.py
```
Metabase at http://localhost:3000. The first Postgres initialization executes `docker/postgres/init/01_schemas.sql`; for **existing** volumes this is NOT automatic. If the smoke test reports missing schemas:
```bash
set -a; source .env; set +a
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < docker/postgres/init/01_schemas.sql
```
After integrating M3, apply `02_staging.sql` similarly if the volume already exists.

## Add these lines to .env locally (do not commit .env)
```dotenv
AIRFLOW_SECRET_KEY=REPLACE_WITH_A_RANDOM_LONG_ALPHANUMERIC_STRING
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=REPLACE_WITH_ANOTHER_STRONG_ALPHANUMERIC_PASSWORD
AIRFLOW_PORT=8080
```
Generate a secret on Mac/Linux with `python3 -c 'import secrets; print(secrets.token_hex(32))'`.

## Week 2 commands
```bash
# Confirm M2+M3 files and staging tables are present.
python3 scripts/m1_check_dag.py
# First-time Airflow build and start:
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow up -d --build airflow-webserver airflow-scheduler
# Check logs and DAG imports:
docker compose -f compose.yaml -f compose.airflow.yaml logs --tail=100 airflow-scheduler
docker compose -f compose.yaml -f compose.airflow.yaml exec airflow-scheduler airflow dags list-import-errors
```
Airflow UI: http://localhost:8080. Login using `.env` admin credentials. Unpause DAG `nyc_taxi_monthly_pipeline`, then **Trigger DAG** with `{ "month": "2025-01" }` (any published month with available taxi/weather data). No automatic schedule is enabled.

### DAG dependencies
```text
ingest_taxi_and_zones -----                           > validate_to_silver -> load_postgres_staging
   ingest_weather --------/                              |
                                                          v
                                verify_output <- build_dbt_warehouse_marts
```
All tasks run **inside the Airflow container**. Source/data is mounted from the host at `/opt/project` and Postgres is addressed by service hostname `postgres:5432`. Never use host `127.0.0.1` from inside a container for Postgres.

### Acceptance
- `docker compose config` validates main stack.
- `scripts/m1_smoke_test.py` shows all four schemas.
- `scripts/m1_check_dag.py` passes static contract checks.
- Airflow scheduler has zero import errors.
- A manual DAG run finishes green and shows nonzero monthly staging taxi records and the `warehouse.fact_trip`/`marts.agg_daily_demand` models.

## Known integration caveats
- The M2 validation script uses DuckDB `INSTALL icu`; the first run requires network/plugin availability. Consider an offline DuckDB extension strategy for offline demos.
- Airflow image package resolution and DAG execution require Docker (not available in this packaging environment); the static tests are **not** end-to-end evidence.
- Airflow metadata shares the local Postgres database for convenience. For production, use a separate metadata DB/user and secret management.
- `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` embeds credentials; protect local `.env` and do not expose ports publicly.
- On repeat runs, loader replaces month data; dbt models are rebuilt, but actual full pipeline rerun has not been verified here.
