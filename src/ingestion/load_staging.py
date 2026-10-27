import argparse
import pandas as pd
import os
import sys
import io
import psycopg2

def load_to_staging(month: str):
    print(f"Loading Silver data for {month} into PostgreSQL staging...")
    
    input_path = os.path.join("data", "silver", "taxi", f"taxi_{month}.parquet")
    
    if not os.path.exists(input_path):
        print(f"Error: Silver file {input_path} not found.")
        sys.exit(1)
        
    print("Reading Silver data...")
    df = pd.read_parquet(input_path)
    print(f"Rows to load: {len(df)}")
    
    # Connect directly using psycopg2
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="nyc_taxi",
        user="taxi_admin",
        password="12345" # <--- MATCH YOUR .env
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    table_name = f"staging.taxi_{month.replace('-', '_')}"
    
    # 1. Drop table if it exists
    cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
    
    # 2. Create the table structure
    cursor.execute(f"""
        CREATE TABLE {table_name} (
            pickup_datetime TIMESTAMPTZ,
            dropoff_datetime TIMESTAMPTZ,
            pickup_location_id BIGINT,
            dropoff_location_id BIGINT,
            trip_distance DOUBLE PRECISION,
            passenger_count DOUBLE PRECISION,
            fare_amount DOUBLE PRECISION,
            total_amount DOUBLE PRECISION,
            source_file TEXT,
            source_row_number BIGINT
        );
    """)
    print(f"Created table {table_name}")

    # 3. Convert DataFrame to CSV in memory
    print("Preparing data for fast copy...")
    output = io.StringIO()
    df.to_csv(output, sep='\t', header=False, index=False, na_rep='\\N')
    output.seek(0)
    
    # 4. Use native COPY command (Blazing fast!)
    print("Copying data into PostgreSQL...")
    cursor.copy_expert(f"COPY {table_name} FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '\\N')", output)
    
    print("Load successful!")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Silver data to Staging")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format")
    args = parser.parse_args()
    
    load_to_staging(args.month)