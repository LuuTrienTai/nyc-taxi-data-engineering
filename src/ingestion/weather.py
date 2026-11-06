import argparse
import calendar
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from src.config import (
    AUDIT_LOG_PATH,
    BRONZE_WEATHER_DIR,
    NYC_LATITUDE,
    NYC_LONGITUDE,
    OPEN_METEO_ARCHIVE_URL,
    ensure_directories,
)
from src.ingestion.taxi import record_audit_log, validate_month_arg


def get_month_date_range(month_str: str) -> tuple[str, str, int]:
    year, month = map(int, month_str.split("-"))
    _, last_day = calendar.monthrange(year, month)
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    expected_hours = last_day * 24
    return start_date, end_date, expected_hours


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=3, max=45),
    retry=retry_if_exception_type((httpx.HTTPError, IOError)),
    reraise=True,
)
def fetch_open_meteo_month(start_date: str, end_date: str) -> dict:
    """
    Requests historical hourly weather in UTC from Open-Meteo.
    Requesting in UTC avoids DST duplicate/missing hour ambiguity in the raw stream;
    America/New_York local time conversion is computed deterministically in Silver.
    """
    params = {
        "latitude": NYC_LATITUDE,
        "longitude": NYC_LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,precipitation,rain,snowfall,wind_speed_10m,weather_code",
        "timezone": "UTC",
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(OPEN_METEO_ARCHIVE_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    if "hourly" not in payload or "time" not in payload["hourly"]:
        raise ValueError("Malformed Open-Meteo response: missing 'hourly.time' key.")

    return payload


def ingest_weather_month(month: str, force: bool = False) -> Path:
    parquet_path = BRONZE_WEATHER_DIR / f"weather_{month}.parquet"
    json_path = BRONZE_WEATHER_DIR / f"weather_{month}.json"

    if parquet_path.exists() and not force:
        meta = pq.read_metadata(parquet_path)
        print(f"[INFO] Weather file already exists at {parquet_path} ({meta.num_rows} hours).")
        return parquet_path

    start_date, end_date, expected_hours = get_month_date_range(month)
    print(f"[INFO] Fetching Open-Meteo hourly weather for {month} ({start_date} to {end_date})...")
    payload = fetch_open_meteo_month(start_date, end_date)

    # Save raw JSON atomically
    tmp_json = json_path.with_suffix(".json.tmp")
    raw_bytes = json.dumps(payload, indent=2).encode("utf-8")
    with open(tmp_json, "wb") as f:
        f.write(raw_bytes)
    os.replace(tmp_json, json_path)

    # Convert hourly arrays to a structured Bronze Parquet table atomically
    hourly = payload["hourly"]
    num_rows = len(hourly["time"])
    if num_rows < expected_hours:
        raise RuntimeError(
            f"Incomplete weather response for {month}: expected {expected_hours} hours, got {num_rows}"
        )

    table = pa.table(
        {
            "observation_time_utc": hourly["time"],
            "temperature_2m": pa.array(hourly.get("temperature_2m"), type=pa.float64()),
            "precipitation": pa.array(hourly.get("precipitation"), type=pa.float64()),
            "rain": pa.array(hourly.get("rain"), type=pa.float64()),
            "snowfall": pa.array(hourly.get("snowfall"), type=pa.float64()),
            "wind_speed_10m": pa.array(hourly.get("wind_speed_10m"), type=pa.float64()),
            "weather_code": pa.array(hourly.get("weather_code"), type=pa.int32()),
            "latitude": [payload.get("latitude", NYC_LATITUDE)] * num_rows,
            "longitude": [payload.get("longitude", NYC_LONGITUDE)] * num_rows,
        }
    )

    tmp_parquet = parquet_path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp_parquet, compression="snappy")
    os.replace(tmp_parquet, parquet_path)

    sha256_hex = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    record_audit_log("bronze_weather", parquet_path, sha256_hex, num_rows)
    print(f"[OK] Saved {parquet_path} ({num_rows} hourly rows, SHA-256: {sha256_hex[:12]}...)")
    return parquet_path


def main() -> int:
    parser = argparse.ArgumentParser(description="M2 Bronze Ingestion: Open-Meteo Historical Weather")
    parser.add_argument("--month", required=True, help="Target month in YYYY-MM format")
    parser.add_argument("--force", action="store_true", help="Overwrite existing Bronze files")
    args = parser.parse_args()

    try:
        ensure_directories()
        month = validate_month_arg(args.month)
        ingest_weather_month(month=month, force=args.force)
        return 0
    except Exception as exc:
        print(f"[ERROR] Weather ingestion failed for month={args.month}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())