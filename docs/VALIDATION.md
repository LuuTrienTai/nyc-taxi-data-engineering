# Project Validation Log — M4 (Dashboard & Analytical Testing)

## 1. Environment & Architecture Overview
*   **Database:** PostgreSQL 16 running via Docker Compose (Project: `nyc-taxi-gold`).
*   **Data Volume:** 3,251,618 valid trips loaded for `2025-01`.
*   **Architecture:** The pipeline strictly follows the `Bronze -> Transient Silver (RAM) -> Gold` design. M2 handles ingestion, M3 handles the `src.pipeline` loading into the `gold` schema, and M4 verifies the results and provides the dashboard.
*   **Dashboard Access:** Served via Docker at `http://localhost:8501`.

## 2. M4 Independent Verification (`src.verify`)
M4's verification script independently queries the database to ensure data integrity, check for architectural violations (leaked Silver tables), and reconcile the fact table against the aggregate marts.

**Command Executed:**
`docker compose run --rm runner python -m src.verify --month 2025-01`

**Output:**
```text
=== Starting M4 Independent Verification for 2025-01 ===
[PASS] gold.fact_trip exists with 3,251,618 rows for 2025-01.
[PASS] No Silver or staging tables found in Postgres.
[PASS] Fact and Mart revenue reconciled: $88,071,527.78

=== All M4 Verification Checks Passed! ===