# M3 — Week 2: dbt warehouse and marts

## Scope
- Build dbt staging views from Week 1 physical staging tables.
- Build `warehouse.dim_zone`, `warehouse.dim_weather_hourly`, `warehouse.fact_trip`.
- Build M4-compatible views `marts.agg_hourly_demand`, `marts.agg_daily_demand`, `marts.agg_zone_demand`.
- Check uniqueness and that dimension joins do not change the trip count.
- **Do not run M4's draft `gold_aggregations.sql`**: it targets a nonexistent `staging.taxi_2026_01`. The dbt models produce the intended marts.

## Prerequisites
1. Finish Week 1: PostgreSQL schema and tables exist, and Silver data is loaded.
2. In repository root, activate Python venv; `pip install -r requirements-m3-week2.txt`.
3. Set credentials from `.env`: `set -a; source .env; set +a` (do not commit credentials).
4. Copy `dbt/profiles.yml.example` to `dbt/profiles.yml` (gitignored; keep credentials in environment).

## Execute
```bash
cd dbt
dbt debug --profiles-dir .
dbt deps --profiles-dir .
dbt build --profiles-dir .
dbt docs generate --profiles-dir .
```
If no taxi data has been loaded, `dbt build` can still create empty tables, but functional acceptance requires a nonempty taxi sample.

## Verify
```bash
# From repository root after returning from dbt directory:
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT COUNT(*) FROM warehouse.fact_trip;'
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT * FROM marts.agg_daily_demand LIMIT 5;'
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT * FROM marts.agg_zone_demand ORDER BY total_trips DESC LIMIT 5;'
```

## Handoff to M4
Query `warehouse.fact_trip` for detailed rows or `marts.agg_*` for chart aggregates. Do not use month-specific staging table names. Pickups are grouped using `pickup_datetime` from the original M2 pipeline (NY local wall clock). Weather joins use UTC-normalized naive timestamps.

## Caveats
- `fact_trip` is a full-refresh dbt table, **not incremental**, suitable for the first three months/prototype but will become expensive as data grows.
- The weather dimension aggregates duplicate UTC hours with `MAX` to preserve key uniqueness; inspect overlapping monthly weather files for contradictory values.
- Zero missing zones/weather is not assumed: unmatched dimension records remain in the fact with NULL enrichment.
- Run `dbt build` after each Week 1 month reload to refresh materialized fact and marts.
