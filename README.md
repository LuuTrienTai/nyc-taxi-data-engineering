# NYC Taxi Data Engineering starter — M1 Week 1

This is a minimal, local-only infrastructure starter. It intentionally **does not** implement ingestion, dbt or Airflow yet.

## Start
1. Install Docker Desktop and Git; open a terminal in this directory.
2. `cp .env.example .env` (on Windows PowerShell: `Copy-Item .env.example .env`).
3. Change `POSTGRES_PASSWORD` in `.env`.
4. `docker compose config`
5. `docker compose up -d`
6. `docker compose ps`
7. `docker compose exec postgres psql -U taxi_admin -d nyc_taxi -c '\dn'` (change user/db if edited).
8. Open http://localhost:3000 and finish Metabase local setup. To add the data warehouse, use host `postgres`, port `5432`, your `.env` username/password and database name.

## Stop
`docker compose down` (keeps database volumes).

**WARNING:** `docker compose down -v` permanently deletes local named volumes, including PostgreSQL data; don't run this for ordinary shutdown.

## Notes
- Compose only exposes ports on localhost; deployment on servers requires an explicit security review.
- The included PostgreSQL init script runs only when its volume is first initialized. For later schema changes use versioned SQL migrations, not edits to an already-run init script.
- Metabase uses embedded H2 for this *local development starter*, not recommended for production. A future project setup may use an independent application database.
- Airflow is planned for Week 2/3 after task contracts are stable.
- Pin/upgrade images after testing with the team's environment; the pinned Metabase image may need adjustment if unavailable for your platform.
