import argparse
import sys
import duckdb

from src.config import (
    BRONZE_TAXI_DIR,
    BRONZE_WEATHER_DIR,
    BRONZE_ZONES_DIR,
    QUARANTINE_TAXI_DIR,
    SILVER_TAXI_DIR,
    SILVER_WEATHER_DIR,
    SILVER_ZONES_DIR,
)

REQUIRED_SILVER_TAXI_COLS = {
    "trip_id",
    "pickup_datetime",
    "dropoff_datetime",
    "pickup_location_id",
    "dropoff_location_id",
    "trip_distance",
    "passenger_count",
    "fare_amount",
    "total_amount",
    "source_file",
    "source_row_number",
}


def run_verification(month: str) -> int:
    con = duckdb.connect(database=":memory:")
    print(f"=== Running M2 Contract & Data Quality Verification for {month} ===")

    # 1. Verify all files exist
    expected_files = [
        BRONZE_TAXI_DIR / f"yellow_tripdata_{month}.parquet",
        BRONZE_WEATHER_DIR / f"weather_{month}.parquet",
        BRONZE_ZONES_DIR / "taxi_zone_lookup.csv",
        SILVER_TAXI_DIR / f"yellow_tripdata_{month}.parquet",
        SILVER_WEATHER_DIR / f"weather_{month}.parquet",
        SILVER_ZONES_DIR / "taxi_zone_lookup.parquet",
        QUARANTINE_TAXI_DIR / f"quarantine_taxi_{month}.parquet",
    ]
    for path in expected_files:
        if not path.exists() or path.stat().st_size == 0:
            raise AssertionError(f"[FAIL] Missing or empty file: {path}")
    print("[PASS] 1. All Bronze, Silver, and Quarantine files exist and are non-empty.")

    silver_taxi = (SILVER_TAXI_DIR / f"yellow_tripdata_{month}.parquet").as_posix()
    quar_taxi = (QUARANTINE_TAXI_DIR / f"quarantine_taxi_{month}.parquet").as_posix()
    bronze_taxi = (BRONZE_TAXI_DIR / f"yellow_tripdata_{month}.parquet").as_posix()

    # 2. Verify Contract B Schema on Silver Taxi
    cols = {
        row[0].lower()
        for row in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{silver_taxi}')").fetchall()
    }
    missing = REQUIRED_SILVER_TAXI_COLS - cols
    if missing:
        raise AssertionError(f"[FAIL] Silver taxi missing Contract B columns: {missing}")
    print("[PASS] 2. Silver taxi schema matches Contract B + deterministic trip_id.")

    # 3. Verify Zero Data Loss (Bronze == Silver + Quarantine)
    b_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{bronze_taxi}')").fetchone()[0]
    s_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{silver_taxi}')").fetchone()[0]
    q_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{quar_taxi}')").fetchone()[0]
    if b_cnt != (s_cnt + q_cnt):
        raise AssertionError(f"[FAIL] Row mismatch! Bronze={b_cnt}, Silver+Quarantine={s_cnt + q_cnt}")
    print(f"[PASS] 3. Row reconciliation exact: {b_cnt:,} Bronze = {s_cnt:,} Silver + {q_cnt:,} Quarantine.")

    # 4. Verify Silver Cleanliness & Uniqueness
    bad_silver = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{silver_taxi}')
        WHERE trip_id IS NULL
           OR dropoff_datetime <= pickup_datetime
           OR fare_amount <= 0
           OR trip_distance <= 0
           OR pickup_location_id NOT BETWEEN 1 AND 263
           OR dropoff_location_id NOT BETWEEN 1 AND 263
    """).fetchone()[0]
    if bad_silver > 0:
        raise AssertionError(f"[FAIL] Found {bad_silver} invalid records leaked into Silver!")

    dup_trips = con.execute(f"""
        SELECT COUNT(*) - COUNT(DISTINCT trip_id) FROM read_parquet('{silver_taxi}')
    """).fetchone()[0]
    if dup_trips > 0:
        raise AssertionError(f"[FAIL] Found {dup_trips} duplicate trip_id keys in Silver!")
    print("[PASS] 4. Silver taxi has 0 invalid records and 100% unique trip_id keys.")

    # 5. Print summary breakdown of Quarantined reasons for M4 (Hùng) & M3 (Ngọc)
    print("\n--- Quarantine Breakdown by Reason ---")
    reasons = con.execute(f"""
        SELECT quarantine_reason, COUNT(*) AS cnt
        FROM read_parquet('{quar_taxi}')
        GROUP BY quarantine_reason
        ORDER BY cnt DESC
    """).fetchall()
    for reason, cnt in reasons:
        print(f"  - {reason}: {cnt:,} rows")

    print("\n=== ALL M2 VERIFICATION CHECKS PASSED SUCCESSFULLY ===")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM")
    args = parser.parse_args()
    try:
        sys.exit(run_verification(args.month))
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)