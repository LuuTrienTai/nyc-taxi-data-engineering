import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import httpx
import pyarrow.parquet as pq
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from src.config import (
    AUDIT_LOG_PATH,
    BRONZE_TAXI_DIR,
    BRONZE_ZONES_DIR,
    TLC_TRIP_BASE_URL,
    TLC_ZONE_LOOKUP_URL,
    bronze_lock,
)


def validate_month_arg(month_str: str) -> str:
    if not re.fullmatch(r"^\d{4}-(0[1-9]|1[0-2])$", month_str):
        raise ValueError(f"Invalid --month format '{month_str}'. Expected YYYY-MM.")
    return month_str


def record_audit_log(dataset: str, target_path: Path, sha256_hex: str, row_count: int) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset": dataset,
        "file_name": target_path.name,
        "file_path": str(target_path),
        "size_bytes": target_path.stat().st_size,
        "sha256": sha256_hex,
        "row_count": row_count,
    }
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPError, IOError)),
    reraise=True,
)
def stream_download_atomic(url: str, dest_path: Path, validate=None) -> str:
    """
    Streams file from URL to a temporary .tmp file, computes SHA-256,
    and performs an atomic rename only after complete download.
    """
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    sha256_hash = hashlib.sha256()

    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            sha256_hash.update(chunk)

        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise IOError(f"Downloaded file is empty: {tmp_path}")

        if validate is not None:
            validate(tmp_path)
        os.replace(tmp_path, dest_path)
        return sha256_hash.hexdigest()

    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def ingest_zones(force: bool = False) -> Path:
    dest_path = BRONZE_ZONES_DIR / "taxi_zone_lookup.csv"
    if dest_path.exists() and not force:
        print(f"[INFO] Zone lookup already exists at {dest_path}. Skipping download.")
        return dest_path

    print(f"[INFO] Downloading Taxi Zone Lookup from {TLC_ZONE_LOOKUP_URL}...")
    sha256_hex = stream_download_atomic(TLC_ZONE_LOOKUP_URL, dest_path)
    with open(dest_path, "r", encoding="utf-8") as f:
        row_count = sum(1 for _ in f) - 1  # Subtract header
    record_audit_log("bronze_zones", dest_path, sha256_hex, row_count)
    print(f"[OK] Saved {dest_path} ({row_count} zones, SHA-256: {sha256_hex[:12]}...)")
    return dest_path


def ingest_taxi_month(month: str, force: bool = False) -> Path:
    filename = f"yellow_tripdata_{month}.parquet"
    url = f"{TLC_TRIP_BASE_URL}/{filename}"
    dest_path = BRONZE_TAXI_DIR / filename

    if dest_path.exists() and not force:
        meta = pq.read_metadata(dest_path)
        print(f"[INFO] Taxi file already exists at {dest_path} ({meta.num_rows:,} rows).")
        return dest_path

    print(f"[INFO] Downloading NYC Yellow Taxi data for {month} from {url}...")
    def row_count_of(path):
        row_count = pq.read_metadata(path).num_rows
        if row_count == 0:
            raise IOError(f'Parquet file has no rows: {path}')
        return row_count

    sha256_hex = stream_download_atomic(url, dest_path, validate=row_count_of)
    row_count = row_count_of(dest_path)

    record_audit_log("bronze_taxi", dest_path, sha256_hex, row_count)
    print(f"[OK] Saved {dest_path} ({row_count:,} rows, SHA-256: {sha256_hex[:12]}...)")
    return dest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="M2 Bronze Ingestion: NYC Yellow Taxi & Zones")
    parser.add_argument("--month", required=True, help="Target month in YYYY-MM format")
    parser.add_argument("--force", action="store_true", help="Overwrite existing Bronze files")
    args = parser.parse_args()

    try:
        month = validate_month_arg(args.month)
        with bronze_lock():
            ingest_zones(force=args.force)
            ingest_taxi_month(month=month, force=args.force)
        return 0
    except Exception as exc:
        print(f"[ERROR] Taxi ingestion failed for month={args.month}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())