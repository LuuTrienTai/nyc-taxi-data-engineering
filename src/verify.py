"""M4 Independent Verification: Checks Gold schema integrity."""
import os
import sys
import psycopg

def verify_month(month: str):
    print(f"=== Starting M4 Independent Verification for {month} ===")
    month_date = f"{month}-01"
    
    try:
        conn = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "taxi_admin"),
            password=os.getenv("POSTGRES_PASSWORD", "taxi_local_demo_2026"),
            dbname=os.getenv("POSTGRES_DB", "nyc_taxi")
        )
        cur = conn.cursor()

        # 1. Check fact_trip exists and has rows
        cur.execute("SELECT to_regclass('gold.fact_trip')")
        if not cur.fetchone()[0]:
            print("[FAIL] gold.fact_trip does not exist!")
            sys.exit(1)
            
        cur.execute("SELECT COUNT(*) FROM gold.fact_trip WHERE data_month = %s", (month_date,))
        count = cur.fetchone()[0]
        print(f"[PASS] gold.fact_trip exists with {count:,} rows for {month}.")
        if count == 0:
            print("[FAIL] fact_trip is empty for this month!")
            sys.exit(1)

        # 2. Check No Silver/Staging Tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema IN ('staging', 'public') AND table_name LIKE '%taxi%'")
        silver_tables = cur.fetchall()
        if silver_tables:
            print(f"[FAIL] Found unexpected staging/Silver tables: {silver_tables}")
            sys.exit(1)
        print("[PASS] No Silver or staging tables found in Postgres.")

        # 3. Reconcile Fact vs Aggregates
        cur.execute("SELECT SUM(total_amount) FROM gold.fact_trip WHERE data_month = %s", (month_date,))
        fact_revenue = cur.fetchone()[0]
        
        cur.execute("SELECT SUM(total_revenue) FROM gold.agg_daily_demand WHERE data_month = %s", (month_date,))
        mart_revenue = cur.fetchone()[0]
        
        if abs(float(fact_revenue) - float(mart_revenue)) > 0.01:
            print(f"[FAIL] Revenue mismatch! Fact: {fact_revenue}, Mart: {mart_revenue}")
            sys.exit(1)
        print(f"[PASS] Fact and Mart revenue reconciled: ${fact_revenue:,.2f}")
        
        print("\n=== All M4 Verification Checks Passed! ===")
        conn.close()
        return 0
        
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        return 1

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM")
    args = parser.parse_args()
    sys.exit(verify_month(args.month))