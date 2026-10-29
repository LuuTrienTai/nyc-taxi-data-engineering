import pandas as pd
import psycopg2
import os
import sys

def run_eda(month_str: str):
    print(f"--- Starting EDA for Month: {month_str} ---")
    
    # 1. Connect to PostgreSQL
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="nyc_taxi",
            user="taxi_admin",
            password="12345" # MATCH YOUR .env
        )
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)
        
    table_name = f"staging.taxi_{month_str.replace('-', '_')}"
    
    # 2. Read a sample of the data (we don't need all 3.6M rows for basic EDA)
    print("Fetching data from PostgreSQL...")
    query = f"SELECT * FROM {table_name} LIMIT 100000"
    df = pd.read_sql(query, con=conn)
    
    if len(df) == 0:
        print(f"No data found in {table_name}. Did you load it?")
        sys.exit(1)
        
    # 3. Verify Dataset Fields (Data Types & Nulls)
    print("\n--- Field Verification ---")
    print(df.dtypes)
    print(f"\nTotal Rows Sampled: {len(df)}")
    print("\nMissing Values per Column:")
    print(df.isnull().sum())
    
    # 4. Basic EDA Statistics
    print("\n--- Basic EDA Statistics ---")
    print(f"Date Range: {df['pickup_datetime'].min()} to {df['pickup_datetime'].max()}")
    print(f"Average Fare: ${df['fare_amount'].mean():.2f}")
    print(f"Average Distance: {df['trip_distance'].mean():.2f} miles")
    print(f"Average Passenger Count: {df['passenger_count'].mean():.2f}")
    
    # 5. Define Analytical KPIs (Grouping)
    print("\n--- Sample KPI 1: Trips by Hour of Day ---")
    df['pickup_hour'] = pd.to_datetime(df['pickup_datetime']).dt.hour
    trips_by_hour = df.groupby('pickup_hour').size().sort_values(ascending=False)
    print(trips_by_hour.head(5)) # Top 5 busiest hours
    
    print("\n--- Sample KPI 2: Top 5 Pickup Zones ---")
    top_zones = df.groupby('pickup_location_id').size().sort_values(ascending=False)
    print(top_zones.head(5))
    
    print("\n--- Sample KPI 3: Revenue by Payment Type (if available) ---")
    # Note: payment_type wasn't in our Silver contract, so let's use total_amount
    print(f"Total Revenue in Sample: ${df['total_amount'].sum():,.2f}")

    conn.close()
    print("\n--- EDA Complete ---")

if __name__ == "__main__":
    # We will test this on January 2026
    run_eda("2026-01")