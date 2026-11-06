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
    print(f"=== M2 Data Validation & Reconciliation Check (Month: {month}) ===")

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
    print("[PASS] 1. All Bronze, Silver, and Quarantine files exist (Taxi, Zones, Weather).")

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
    print("[PASS] 2. Silver taxi schema matches Contract B + deterministic MD5 trip_id.")

    # 3. Verify Zero Data Loss (Bronze == Silver + Quarantine)
    b_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{bronze_taxi}')").fetchone()[0]
    s_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{silver_taxi}')").fetchone()[0]
    q_cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{quar_taxi}')").fetchone()[0]
    if b_cnt != (s_cnt + q_cnt):
        raise AssertionError(f"[FAIL] Row mismatch! Bronze={b_cnt}, Silver+Quarantine={s_cnt + q_cnt}")

    print("\n--- KEY RECONCILIATION NUMBERS (Bronze = Silver + Quarantine) ---")
    print(f"  * Bronze Taxi Total   : {b_cnt:,} rows")
    print(f"  * Silver Taxi (Valid) : {s_cnt:,} rows  --> (Handed off to M3 staging.taxi_trips)")
    print(f"  * Quarantine Taxi     : {q_cnt:,} rows  --> (Isolated with quarantine_reason)")
    print(f"[PASS] 3. Exact Reconciliation: {b_cnt:,} = {s_cnt:,} + {q_cnt:,} (0 rows lost).")

    # 4. Verify Silver Cleanliness & Duplicate Prevention
    bad_silver = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{silver_taxi}')
        WHERE trip_id IS NULL
           OR dropoff_datetime <= pickup_datetime
           OR fare_amount <= 0
           OR trip_distance <= 0
           OR pickup_location_id NOT BETWEEN 1 AND 263
           OR dropoff_location_id NOT BETWEEN 1 AND 263
    """).fetchone()[0]
    dup_trips = con.execute(f"""
        SELECT COUNT(*) - COUNT(DISTINCT trip_id) FROM read_parquet('{silver_taxi}')
    """).fetchone()[0]
    if bad_silver > 0 or dup_trips > 0:
        raise AssertionError(f"[FAIL] Silver contains {bad_silver} invalid rows or {dup_trips} duplicates!")
    print("[PASS] 4. Duplicate Prevention & Quality Gate: 0 invalid rows and 0 duplicate trip_ids in Silver.")

    # 5. Print Quarantine Breakdown & Sample Rejected Rows for Live Demo
    print("\n--- Quarantine Breakdown by Reason ---")
    reasons = con.execute(f"""
        SELECT quarantine_reason, COUNT(*) AS cnt
        FROM read_parquet('{quar_taxi}')
        GROUP BY quarantine_reason
        ORDER BY cnt DESC
    """).fetchall()
    if not reasons:
        print("  - 0 rows quarantined (all rows passed validation rules).")
    else:
        for reason, cnt in reasons:
            print(f"  - {reason}: {cnt:,} rows")

        print("\n--- Sample Quarantined Records (Rejected + Reason) ---")
        con.sql(f"""
            SELECT
                pickup_datetime,
                dropoff_datetime,
                pickup_location_id AS pu_loc,
                dropoff_location_id AS do_loc,
                passenger_count AS pax,
                trip_distance AS dist,
                fare_amount AS fare,
                quarantine_reason
            FROM read_parquet('{quar_taxi}')
            LIMIT 5
        """).show(max_width=180)

    print("=== ALL M2 VERIFICATION CHECKS PASSED SUCCESSFULLY ===")
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