import pandas as pd
import psycopg2
import sys

def run_eda(month_str: str):
    print(f"--- Starting EDA for Month: {month_str} ---")
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432, dbname="nyc_taxi",
            user="taxi_admin", password="12345"
        )
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)
        
    table_name = f"staging.taxi_{month_str.replace('-', '_')}"
    query = f"SELECT * FROM {table_name} LIMIT 100000"
    df = pd.read_sql(query, con=conn)
    
    if len(df) == 0:
        print(f"No data found in {table_name}.")
        sys.exit(1)
        
    print("\n--- Field Verification ---")
    print(df.dtypes)
    print(f"\nMissing Values:\n{df.isnull().sum()}")
    
    print("\n--- Basic EDA Statistics ---")
    print(f"Date Range: {df['pickup_datetime'].min()} to {df['pickup_datetime'].max()}")
    print(f"Average Fare: ${df['fare_amount'].mean():.2f}")
    print(f"Average Distance: {df['trip_distance'].mean():.2f} miles")
    
    print("\n--- Sample KPI 1: Trips by Hour of Day ---")
    df['pickup_hour'] = pd.to_datetime(df['pickup_datetime']).dt.hour
    print(df.groupby('pickup_hour').size().sort_values(ascending=False).head(5))
    
    print("\n--- Sample KPI 2: Top 5 Pickup Zones ---")
    print(df.groupby('pickup_location_id').size().sort_values(ascending=False).head(5))
    
    conn.close()
    print("\n--- EDA Complete ---")

if __name__ == "__main__":
    run_eda("2026-01")