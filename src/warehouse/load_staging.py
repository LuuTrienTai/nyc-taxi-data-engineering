"""Load M2 Silver Parquet into Postgres with transaction-scoped replacement.

Run from repository root: python -m src.warehouse.load_staging --month 2025-01
"""
import argparse
import os
import re
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import psycopg
from psycopg import sql

from src.config import SILVER_TAXI_DIR, SILVER_WEATHER_DIR, SILVER_ZONES_DIR

TABLES = {
    "taxi": (
        "taxi_trips",
        ["trip_id", "pickup_datetime", "dropoff_datetime", "pickup_datetime_utc",
         "weather_hour_utc", "observation_hour_ny", "pickup_location_id",
         "dropoff_location_id", "trip_distance", "passenger_count", "fare_amount",
         "tip_amount", "total_amount", "vendor_id", "payment_type_id", "rate_code_id",
         "source_file", "source_row_number"],
    ),
    "weather": (
        "weather_hourly",
        ["observation_hour_utc", "observation_hour_ny", "temperature_c",
         "precipitation_mm", "rain_mm", "snowfall_cm", "wind_speed_kmh",
         "weather_code", "latitude", "longitude", "source_file", "source_row_number"],
    ),
    "zones": (
        "zones",
        ["location_id", "borough", "zone_name", "service_zone", "source_file",
         "source_row_number"],
    ),
}


def parse_month(month: str) -> date:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("--month must use YYYY-MM")
    year, mon = map(int, month.split("-"))
    return date(year, mon, 1)


def connection_kwargs() -> dict:
    """Use same env vars as the team's compose.yaml, locally on 127.0.0.1."""
    return {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "taxi_admin"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "dbname": os.getenv("POSTGRES_DB", "nyc_taxi"),
        "connect_timeout": 10,
    }


def require_columns(path: Path, cols: list[str]) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"Required M2 Silver file missing: {path}")
    p = pq.ParquetFile(path)
    absent = set(cols) - set(p.schema_arrow.names)
    if absent:
        raise ValueError(f"{path}: missing Silver columns {sorted(absent)}")
    return p.metadata.num_rows


def load_one(conn: psycopg.Connection, dataset: str, path: Path, month: date) -> int:
    table, cols = TABLES[dataset]
    expected = require_columns(path, cols)
    extra_cols = [] if dataset == "zones" else ["data_month"]
    copy_columns = cols + extra_cols
    # Entire replacement stays in a transaction; failure rolls back to previous data.
    with conn.cursor() as cur:
        if dataset == "zones":
            cur.execute("DELETE FROM staging.zones")
        else:
            cur.execute(sql.SQL("DELETE FROM staging.{} WHERE data_month = %s").format(sql.Identifier(table)), (month,))

        copy_stmt = sql.SQL("COPY staging.{} ({}) FROM STDIN").format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, copy_columns))
        )
        count = 0
        with cur.copy(copy_stmt) as writer:
            pf = pq.ParquetFile(path)
            for batch in pf.iter_batches(batch_size=5000, columns=cols):
                for record in batch.to_pylist():
                    values = [record[c] for c in cols]
                    if dataset != "zones":
                        values.append(month)
                    writer.write_row(tuple(values))
                    count += 1

        if count != expected:
            raise RuntimeError(f"Count mismatch for {dataset}: {count} != {expected}")
        if dataset != "zones":
            cur.execute(
                """INSERT INTO audit.monthly_loads(dataset, data_month, source_file, rows_loaded)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (dataset, data_month) DO UPDATE SET
                       source_file = EXCLUDED.source_file,
                       rows_loaded = EXCLUDED.rows_loaded,
                       loaded_at = now()""",
                (dataset, month, path.name, count),
            )
        return count


def main() -> int:
    parser = argparse.ArgumentParser(description="M3: Silver Parquet to PostgreSQL staging")
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--dataset", choices=["all", "taxi", "weather", "zones"], default="all")
    args = parser.parse_args()
    try:
        month = parse_month(args.month)
        paths = {
            "taxi": SILVER_TAXI_DIR / f"yellow_tripdata_{args.month}.parquet",
            "weather": SILVER_WEATHER_DIR / f"weather_{args.month}.parquet",
            "zones": SILVER_ZONES_DIR / "taxi_zone_lookup.parquet",
        }
        names = list(TABLES) if args.dataset == "all" else [args.dataset]
        # Preflight all inputs: avoid destructive modification on missing files.
        for name in names:
            require_columns(paths[name], TABLES[name][1])
        with psycopg.connect(**connection_kwargs()) as conn:
            # Check table existence before attempting load; schema initialized by SQL.
            for name in names:
                with conn.transaction():
                    count = load_one(conn, name, paths[name], month)
                print(f"[OK] staging.{TABLES[name][0]}: {count:,} rows ({args.month})")
        return 0
    except Exception as exc:
        print(f"[ERROR] M3 load failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
