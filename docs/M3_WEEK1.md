# M3 — Week 1: PostgreSQL staging

## Ownership
- `docker/postgres/init/02_staging.sql`: PostgreSQL staging definitions (taxi, weather, zones), audit load table.
- `src/warehouse/load_staging.py`: transactional Silver -> staging loader.
- `requirements-m3.txt`: loader dependencies.

No changes to M2 ingestion/validation and no changes to M1 compose.yaml.

## Prerequisites
1. `cp .env.example .env`, then set a local Postgres password.
2. `docker compose up -d` and check `docker compose ps`.
3. `python3 -m venv .venv && source .venv/bin/activate`
4. `pip install -r requirements-m3.txt`
5. `set -a; source .env; set +a` (macOS/Linux; avoid committing `.env`).

**Existing database volume:** Postgres runs init scripts only at first creation. If your volume already exists, apply schema manually:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < docker/postgres/init/02_staging.sql
```

Do NOT use `docker compose down -v` to apply schema, as it destroys data.

## Load
M2 first generates the three Silver files:
- `data/silver/taxi/yellow_tripdata_YYYY-MM.parquet`
- `data/silver/weather/weather_YYYY-MM.parquet`
- `data/silver/zones/taxi_zone_lookup.parquet`

Then run:

```bash
python -m src.warehouse.load_staging --month 2025-01
# For a smaller partial test:
python -m src.warehouse.load_staging --month 2025-01 --dataset zones
```

The loader replaces the selected month (or entire zones table) transactionally, so reruns do not append duplicates. Each dataset's transaction is independent; `--dataset all` may partially succeed at the dataset level if a later dataset fails. Tables are intentionally **staging**, not final Gold marts.

## Verify
```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT count(*) FROM staging.taxi_trips;'
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT count(*) FROM staging.weather_hourly;'
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT count(*) FROM staging.zones;'
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT dataset, data_month, rows_loaded FROM audit.monthly_loads;'
```

## Contract considerations
- Silver's `*_utc` columns are timezone-normalized, **timestamp without time zone**. They represent UTC wall-clock timestamps. Do not interpret these in a different local timezone when joining.
- `trip_id` is M2's deterministic MD5 surrogate; M2 validation deduplicates records within a month. `PRIMARY KEY (data_month, trip_id)` protects against duplicates.
- Loading 3 months may take time for millions of rows because `COPY.write_row()` is per row, though data is streamed in batches.
- A `data_month` key is added by the loader and is not required in M2 Silver.
- Weather and zone table names follow current Silver outputs; coordinate any future changes with M2 and M4.
