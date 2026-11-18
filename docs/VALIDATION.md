# Project Validation Log (M4 Compiled)

## 1. Environment & Architecture Verification
*   **Database:** PostgreSQL running via Docker Compose.
*   **Gold Layer:** `warehouse.fact_trip`.
*   **Row Count:** 2,791,097 valid trip records loaded for 2025-01.

## 2. M2 & M3 Pipeline Execution Results (Executed by M4)
*   **M2 Taxi Ingestion:** Downloaded 3,475,226 rows (Bronze).
*   **M2 Validation:** 2,791,097 rows passed to Silver, 684,129 rows quarantined (19.69%).
*   **M3 Staging:** Loaded 2,791,097 rows into `staging.taxi_trips`.

## 3. M4 Independent Verification (`src.verify`)
Command: `python -m src.verify`

**Output:**
```text
=== Starting M4 Independent Verification ===
[PASS] warehouse.fact_trip exists with 2,791,097 rows.
[PASS] No Silver tables found in Postgres (Silver is in RAM only).
[INFO] Total Trips: 2,791,097
[INFO] Total Revenue: $75,450,834.17