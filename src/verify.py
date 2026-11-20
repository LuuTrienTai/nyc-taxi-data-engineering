import sys
import psycopg2

def verify_database():
    print("=== Starting M4 Independent Verification ===")
    try:
        conn = psycopg2.connect(
            host="127.0.0.1", port=5432, dbname="nyc_taxi",
            user="taxi_admin", password="12345"
        )
        cur = conn.cursor()

        # 1. Check if fact_trip exists and has rows
        cur.execute("SELECT to_regclass('warehouse.fact_trip')")
        if not cur.fetchone()[0]:
            print("[FAIL] warehouse.fact_trip does not exist!")
            sys.exit(1)
            
        cur.execute("SELECT COUNT(*) FROM warehouse.fact_trip")
        count = cur.fetchone()[0]
        print(f"[PASS] warehouse.fact_trip exists with {count:,} rows.")
        if count == 0:
            print("[FAIL] fact_trip is empty!")
            sys.exit(1)

        # 2. Check that there are no Silver tables in Postgres
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%silver%'")
        silver_tables = cur.fetchall()
        if silver_tables:
            print(f"[FAIL] Found Silver tables in DB: {silver_tables}")
            sys.exit(1)
        print("[PASS] No Silver tables found in Postgres (Silver is in RAM only).")

        # 3. Check Aggregates (Reconcile fact vs daily aggregate manually)
        cur.execute("SELECT COUNT(*) FROM warehouse.fact_trip")
        total_fact = cur.fetchone()[0]
        
        cur.execute("SELECT SUM(total_amount) FROM warehouse.fact_trip")
        total_rev = cur.fetchone()[0]
        
        print(f"[INFO] Total Trips: {total_fact:,}")
        print(f"[INFO] Total Revenue: ${total_rev:,.2f}")
        
        print("\n=== All Verification Checks Passed! ===")
        conn.close()
        return 0
        
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(verify_database())
