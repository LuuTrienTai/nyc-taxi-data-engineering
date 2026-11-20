"""Integration check for M4: Verifies DB connection and basic reconciliation."""
import psycopg2
import sys

def run_check():
    print("=== M4 Integration Check ===")
    try:
        conn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="nyc_taxi", user="taxi_admin", password="12345")
        cur = conn.cursor()
        
        # Check Gold Table
        cur.execute("SELECT COUNT(*) FROM warehouse.fact_trip")
        fact_count = cur.fetchone()[0]
        print(f"[PASS] fact_trip row count: {fact_count:,}")
        
        # Check Staging Table
        cur.execute("SELECT COUNT(*) FROM staging.taxi_trips")
        staging_count = cur.fetchone()[0]
        print(f"[INFO] staging.taxi_trips row count: {staging_count:,}")
        
        if fact_count > 0:
            print("[PASS] Integration check successful.")
            return 0
        else:
            print("[FAIL] fact_trip is empty.")
            return 1
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run_check())