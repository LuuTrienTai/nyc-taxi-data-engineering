# NYC Taxi team integration contracts — draft v1

## Scope
- Yellow Taxi data, initial one-month sample, later three consecutive months.
- Zone lookup and Open-Meteo historical weather covering the taxi period.
- Reporting timezone: America/New_York. Store timezone-aware instants when possible; document DST ambiguity and hourly aggregation policy.

## Data files
- Bronze: `data/bronze/{taxi,weather,zones}/` preserves original source files.
- Silver: `data/silver/{taxi,weather,zones}/` holds validated Parquet.
- Quarantine: `data/quarantine/` holds rejected rows plus reason code.
- Monthly Silver file example: `data/silver/taxi/taxi_YYYY-MM.parquet`.

## Proposed Silver taxi columns
pickup_datetime, dropoff_datetime, pickup_location_id, dropoff_location_id, trip_distance, passenger_count, fare_amount, total_amount, source_file, source_row_number.
Document exact PostgreSQL/Arrow types and null policy before implementation.

## Proposed CLI interfaces (not implemented yet)
- `python -m src.ingestion.taxi --month YYYY-MM`
- `python -m src.ingestion.weather --month YYYY-MM`
- `python -m src.processing.validate --month YYYY-MM`
Return exit code 0 on success, nonzero on failure. No partially published files: write temp output and atomically move after validation.

## PostgreSQL namespaces
- `staging`: incoming normalized rows and load work area.
- `warehouse`: `fact_trip`, dimensions.
- `marts`: read-oriented Gold models consumed by Metabase.
- `audit`: pipeline runs and later source file tracking.

## Retry contract
- Identify source versions by original URL/path + checksum.
- Preserve source row position when transforming trips.
- Prefer transactional replace-by-month (or carefully scoped merge) rather than blind append.
- Successful re-run of unchanged input must leave all published metrics unchanged.

## Member ownership
- M1: compose, integration, orchestration, observability.
- M2: ingestion, quality, Bronze/Silver and quarantine.
- M3: staging/warehouse/marts/dbt models and transactional loading.
- M4: EDA, dashboard, SQL KPI checks and analytical testing.

## Acceptance for week one
- `docker compose config` succeeds.
- PostgreSQL healthy, schemas exist, metabase reachable.
- A local test query can be executed against PostgreSQL.
- M2, M3, M4 agree on the final Silver data contract.
