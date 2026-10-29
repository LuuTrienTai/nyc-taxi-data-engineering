import argparse
import os
import sys
from pathlib import Path

import duckdb

from src.config import (
    BRONZE_TAXI_DIR,
    BRONZE_WEATHER_DIR,
    BRONZE_ZONES_DIR,
    QUARANTINE_TAXI_DIR,
    QUARANTINE_WEATHER_DIR,
    QUARANTINE_ZONES_DIR,
    SILVER_TAXI_DIR,
    SILVER_WEATHER_DIR,
    SILVER_ZONES_DIR,
    ensure_directories,
)
from src.ingestion.taxi import validate_month_arg

REQUIRED_TAXI_COLUMNS = {
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "pulocationid",
    "dolocationid",
    "trip_distance",
    "passenger_count",
    "fare_amount",
    "total_amount",
}


def atomic_duckdb_copy(con: duckdb.DuckDBPyConnection, query: str, dest_path: Path) -> int:
    """Executes a DuckDB query to a temporary Parquet file and atomically renames it."""
    tmp_path = dest_path.with_suffix(".parquet.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    con.execute(f"COPY ({query}) TO '{tmp_path.as_posix()}' (FORMAT PARQUET, COMPRESSION SNAPPY)")
    count_row = con.execute(f"SELECT COUNT(*) FROM read_parquet('{tmp_path.as_posix()}')").fetchone()
    row_count = count_row[0] if count_row else 0
    os.replace(tmp_path, dest_path)
    return row_count


def validate_and_process_zones(con: duckdb.DuckDBPyConnection) -> None:
    bronze_zones = BRONZE_ZONES_DIR / "taxi_zone_lookup.csv"
    if not bronze_zones.exists():
        raise FileNotFoundError(f"Missing Bronze zones file: {bronze_zones}")

    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_zones AS
        SELECT
            CAST(LocationID AS INTEGER) AS location_id,
            TRIM(CAST(Borough AS VARCHAR)) AS borough,
            TRIM(CAST(Zone AS VARCHAR)) AS zone_name,
            TRIM(CAST(service_zone AS VARCHAR)) AS service_zone,
            '{bronze_zones.name}' AS source_file,
            ROW_NUMBER() OVER () AS source_row_number,
            CASE
                WHEN LocationID IS NULL THEN 'NULL_LOCATION_ID'
                WHEN LocationID NOT BETWEEN 1 AND 263 THEN 'UNKNOWN_OR_OUT_OF_RANGE_ZONE_ID'
                WHEN Borough IS NULL OR TRIM(Borough) IN ('', 'Unknown', 'N/A') THEN 'UNKNOWN_BOROUGH'
                WHEN Zone IS NULL OR TRIM(Zone) IN ('', 'NV', 'NA') THEN 'UNKNOWN_ZONE_NAME'
                ELSE NULL
            END AS quarantine_reason
        FROM read_csv_auto('{bronze_zones.as_posix()}', header=True)
    """)

    silver_path = SILVER_ZONES_DIR / "taxi_zone_lookup.parquet"
    quarantine_path = QUARANTINE_ZONES_DIR / "quarantine_zones.parquet"

    silver_cnt = atomic_duckdb_copy(
        con,
        "SELECT location_id, borough, zone_name, service_zone, source_file, source_row_number "
        "FROM raw_zones WHERE quarantine_reason IS NULL",
        silver_path,
    )
    quar_cnt = atomic_duckdb_copy(
        con,
        "SELECT * FROM raw_zones WHERE quarantine_reason IS NOT NULL",
        quarantine_path,
    )
    print(f"[OK] Zones validated -> Silver: {silver_cnt} rows | Quarantine: {quar_cnt} rows")


def validate_and_process_weather(con: duckdb.DuckDBPyConnection, month: str) -> None:
    bronze_weather = BRONZE_WEATHER_DIR / f"weather_{month}.parquet"
    if not bronze_weather.exists():
        raise FileNotFoundError(f"Missing Bronze weather file: {bronze_weather}")

    con.execute("INSTALL icu; LOAD icu;")
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_weather AS
        WITH parsed AS (
            SELECT
                CAST(observation_time_utc AS TIMESTAMP) AT TIME ZONE 'UTC' AS obs_timestamptz,
                CAST(temperature_2m AS DOUBLE) AS temperature_c,
                CAST(precipitation AS DOUBLE) AS precipitation_mm,
                CAST(rain AS DOUBLE) AS rain_mm,
                CAST(snowfall AS DOUBLE) AS snowfall_cm,
                CAST(wind_speed_10m AS DOUBLE) AS wind_speed_kmh,
                CAST(weather_code AS INTEGER) AS weather_code,
                CAST(latitude AS DOUBLE) AS latitude,
                CAST(longitude AS DOUBLE) AS longitude,
                '{bronze_weather.name}' AS source_file,
                ROW_NUMBER() OVER () AS source_row_number
            FROM read_parquet('{bronze_weather.as_posix()}')
        )
        SELECT
            obs_timestamptz AT TIME ZONE 'UTC' AS observation_hour_utc,
            obs_timestamptz AT TIME ZONE 'America/New_York' AS observation_hour_ny,
            temperature_c,
            precipitation_mm,
            rain_mm,
            snowfall_cm,
            wind_speed_kmh,
            weather_code,
            latitude,
            longitude,
            source_file,
            source_row_number,
            CASE
                WHEN obs_timestamptz IS NULL THEN 'NULL_OBSERVATION_TIME'
                WHEN temperature_c IS NULL OR temperature_c NOT BETWEEN -50.0 AND 60.0 THEN 'INVALID_TEMPERATURE'
                WHEN precipitation_mm IS NULL OR precipitation_mm < 0.0 THEN 'NEGATIVE_OR_NULL_PRECIPITATION'
                ELSE NULL
            END AS quarantine_reason
        FROM parsed
    """)

    silver_path = SILVER_WEATHER_DIR / f"weather_{month}.parquet"
    quarantine_path = QUARANTINE_WEATHER_DIR / f"quarantine_weather_{month}.parquet"

    silver_cnt = atomic_duckdb_copy(
        con,
        """
        SELECT
            observation_hour_utc,
            observation_hour_ny,
            temperature_c,
            precipitation_mm,
            rain_mm,
            snowfall_cm,
            wind_speed_kmh,
            weather_code,
            latitude,
            longitude,
            source_file,
            source_row_number
        FROM raw_weather
        WHERE quarantine_reason IS NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY observation_hour_utc ORDER BY source_row_number) = 1
        """,
        silver_path,
    )
    quar_cnt = atomic_duckdb_copy(
        con,
        "SELECT * FROM raw_weather WHERE quarantine_reason IS NOT NULL",
        quarantine_path,
    )
    print(f"[OK] Weather ({month}) validated -> Silver: {silver_cnt} rows | Quarantine: {quar_cnt} rows")


def validate_and_process_taxi(con: duckdb.DuckDBPyConnection, month: str) -> None:
    bronze_taxi = BRONZE_TAXI_DIR / f"yellow_tripdata_{month}.parquet"
    if not bronze_taxi.exists():
        raise FileNotFoundError(f"Missing Bronze taxi file: {bronze_taxi}")

    # Stage 3 Circuit Breaker: Check column schema before processing
    schema_rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{bronze_taxi.as_posix()}')").fetchall()
    actual_cols = {row[0].lower() for row in schema_rows}
    missing_cols = REQUIRED_TAXI_COLUMNS - actual_cols
    if missing_cols:
        raise RuntimeError(f"Schema circuit breaker triggered! Missing required columns: {missing_cols}")

    year, mon = map(int, month.split("-"))
    month_start = f"{year:04d}-{mon:02d}-01 00:00:00"
    next_year, next_mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
    month_end = f"{next_year:04d}-{next_mon:02d}-01 00:00:00"

    con.execute("INSTALL icu; LOAD icu;")
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW evaluated_taxi AS
        WITH raw_numbered AS (
            SELECT
                CAST(VendorID AS INTEGER) AS vendor_id,
                CAST(tpep_pickup_datetime AS TIMESTAMP) AS pickup_datetime,
                CAST(tpep_dropoff_datetime AS TIMESTAMP) AS dropoff_datetime,
                CAST(PULocationID AS INTEGER) AS pickup_location_id,
                CAST(DOLocationID AS INTEGER) AS dropoff_location_id,
                CAST(trip_distance AS DOUBLE) AS trip_distance,
                CAST(passenger_count AS INTEGER) AS passenger_count,
                CAST(fare_amount AS DOUBLE) AS fare_amount,
                CAST(tip_amount AS DOUBLE) AS tip_amount,
                CAST(total_amount AS DOUBLE) AS total_amount,
                CAST(payment_type AS INTEGER) AS payment_type_id,
                CAST(RatecodeID AS INTEGER) AS rate_code_id,
                '{bronze_taxi.name}' AS source_file,
                ROW_NUMBER() OVER () AS source_row_number
            FROM read_parquet('{bronze_taxi.as_posix()}')
        ),
        enriched AS (
            SELECT
                -- Deterministic MD5 Surrogate Key (Issue 3 Defense)
                MD5(
                    COALESCE(STRFTIME(pickup_datetime, '%Y-%m-%dT%H:%M:%S.%f'), '_NULL_') || '||' ||
                    COALESCE(STRFTIME(dropoff_datetime, '%Y-%m-%dT%H:%M:%S.%f'), '_NULL_') || '||' ||
                    COALESCE(CAST(pickup_location_id AS VARCHAR), '_NULL_') || '||' ||
                    COALESCE(CAST(dropoff_location_id AS VARCHAR), '_NULL_') || '||' ||
                    COALESCE(PRINTF('%.2f', fare_amount), '_NULL_')
                ) AS trip_id,
                vendor_id,
                pickup_datetime,
                dropoff_datetime,
                -- Normalize America/New_York wall-clock time to UTC for DST-safe joins
                (pickup_datetime AT TIME ZONE 'America/New_York') AT TIME ZONE 'UTC' AS pickup_datetime_utc,
                DATE_TRUNC('hour', (pickup_datetime AT TIME ZONE 'America/New_York') AT TIME ZONE 'UTC') AS weather_hour_utc,
                DATE_TRUNC('hour', pickup_datetime) AS observation_hour_ny,
                pickup_location_id,
                dropoff_location_id,
                trip_distance,
                passenger_count,
                fare_amount,
                tip_amount,
                total_amount,
                payment_type_id,
                rate_code_id,
                source_file,
                source_row_number,
                EPOCH(dropoff_datetime - pickup_datetime) / 3600.0 AS duration_hours
            FROM raw_numbered
        ),
        dedup_flagged AS (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY trip_id ORDER BY source_row_number) AS duplicate_rank
            FROM enriched
        )
        SELECT
            *,
            CASE
                WHEN pickup_datetime IS NULL OR dropoff_datetime IS NULL THEN 'NULL_TIMESTAMPS'
                WHEN dropoff_datetime <= pickup_datetime THEN 'INVERTED_OR_ZERO_DURATION_TIMESTAMPS'
                WHEN pickup_datetime < CAST('{month_start}' AS TIMESTAMP)
                  OR pickup_datetime >= CAST('{month_end}' AS TIMESTAMP) THEN 'OUT_OF_MONTH_DRIFT'
                WHEN pickup_location_id IS NULL OR pickup_location_id NOT BETWEEN 1 AND 263 THEN 'INVALID_PICKUP_LOCATION_ID'
                WHEN dropoff_location_id IS NULL OR dropoff_location_id NOT BETWEEN 1 AND 263 THEN 'INVALID_DROPOFF_LOCATION_ID'
                WHEN passenger_count IS NULL OR passenger_count NOT BETWEEN 1 AND 9 THEN 'INVALID_PASSENGER_COUNT'
                WHEN trip_distance IS NULL OR trip_distance <= 0.0 OR trip_distance > 300.0 THEN 'INVALID_TRIP_DISTANCE'
                WHEN fare_amount IS NULL OR fare_amount <= 0.0 OR fare_amount > 5000.0 THEN 'INVALID_FARE_AMOUNT'
                WHEN total_amount IS NULL OR total_amount <= 0.0 THEN 'INVALID_TOTAL_AMOUNT'
                WHEN duration_hours > 0.0167 AND (trip_distance / duration_hours) > 100.0 THEN 'EXCEEDS_MAX_VELOCITY_100MPH'
                WHEN duplicate_rank > 1 THEN 'DUPLICATE_SURROGATE_TRIP_ID'
                ELSE NULL
            END AS quarantine_reason
        FROM dedup_flagged
    """)

    silver_path = SILVER_TAXI_DIR / f"yellow_tripdata_{month}.parquet"
    quarantine_path = QUARANTINE_TAXI_DIR / f"quarantine_taxi_{month}.parquet"

    # Write Conformed Silver Parquet (Strictly satisfies Contract B schema + surrogate key)
    silver_cnt = atomic_duckdb_copy(
        con,
        """
        SELECT
            trip_id,
            pickup_datetime,
            dropoff_datetime,
            pickup_datetime_utc,
            weather_hour_utc,
            observation_hour_ny,
            pickup_location_id,
            dropoff_location_id,
            trip_distance,
            passenger_count,
            fare_amount,
            tip_amount,
            total_amount,
            vendor_id,
            payment_type_id,
            rate_code_id,
            source_file,
            source_row_number
        FROM evaluated_taxi
        WHERE quarantine_reason IS NULL
        """,
        silver_path,
    )

    # Write Rejected Quarantine Parquet with quarantine_reason
    quar_cnt = atomic_duckdb_copy(
        con,
        """
        SELECT
            trip_id,
            pickup_datetime,
            dropoff_datetime,
            pickup_location_id,
            dropoff_location_id,
            trip_distance,
            passenger_count,
            fare_amount,
            total_amount,
            source_file,
            source_row_number,
            quarantine_reason
        FROM evaluated_taxi
        WHERE quarantine_reason IS NOT NULL
        """,
        quarantine_path,
    )

    total_bronze = con.execute(f"SELECT COUNT(*) FROM read_parquet('{bronze_taxi.as_posix()}')").fetchone()[0]
    if silver_cnt + quar_cnt != total_bronze:
        raise RuntimeError(
            f"Row reconciliation failure! Bronze ({total_bronze}) != Silver ({silver_cnt}) + Quarantine ({quar_cnt})"
        )

    print(
        f"[OK] Taxi ({month}) validated -> Bronze: {total_bronze:,} | "
        f"Silver: {silver_cnt:,} | Quarantine: {quar_cnt:,} ({quar_cnt / total_bronze * 100:.2f}%)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="M2 Processing: Validate Bronze -> Silver & Quarantine")
    parser.add_argument("--month", required=True, help="Target month in YYYY-MM format")
    args = parser.parse_args()

    try:
        ensure_directories()
        month = validate_month_arg(args.month)
        con = duckdb.connect(database=":memory:")
        validate_and_process_zones(con)
        validate_and_process_weather(con, month)
        validate_and_process_taxi(con, month)
        con.close()
        return 0
    except Exception as exc:
        print(f"[ERROR] Validation failed for month={args.month}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())