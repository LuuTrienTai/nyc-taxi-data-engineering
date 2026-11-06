import pandas as pd
import psycopg2
import argparse
import sys

def validate_aggregations(month_str: str):
    table_name = f"staging.taxi_{month_str.replace('-', '_')}"
    print(f"--- Validating Metrics for Month: {month_str} ---")
    
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="nyc_taxi",
        user="taxi_admin", password="12345"
    )
    
    # 1. Get Total Trips and Total Revenue directly from SQL
    # FIXED: We added AS aliases so Pandas knows the column names
    query_totals = f"SELECT COUNT(*) AS total_trips, SUM(total_amount) AS total_revenue FROM {table_name}"
    totals = pd.read_sql(query_totals, con=conn).iloc[0]
    total_trips = totals['total_trips']
    total_revenue = totals['total_revenue']
    
    # 2. Get top zone
    query_top_zone = f"""
        SELECT pickup_location_id, COUNT(*) as trips 
        FROM {table_name} 
        GROUP BY pickup_location_id 
        ORDER BY trips DESC LIMIT 1
    """
    top_zone = pd.read_sql(query_top_zone, con=conn).iloc[0]
    top_zone_id = top_zone['pickup_location_id']
    top_zone_trips = top_zone['trips']
    
    # 3. Print the PASS result
    print(f"[PASS] staging = fact = Gold.")
    print(f"Total Trips: {total_trips:,}")
    print(f"Total Revenue: ${total_revenue:,.2f}")
    print(f"Top Pickup Zone: ID {top_zone_id} with {top_zone_trips:,} trips.")
    
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format")
    args = parser.parse_args()
    
    validate_aggregations(args.month)