import argparse
import pandas as pd
import os
import sys

def validate_taxi_data(month: str):
    print(f"Starting validation for month: {month}")
    
    # 1. Define paths
    input_path = os.path.join("data", "bronze", "taxi", f"yellow_tripdata_{month}.parquet")
    output_dir = os.path.join("data", "silver", "taxi")
    output_path = os.path.join(output_dir, f"taxi_{month}.parquet")
    
    if not os.path.exists(input_path):
        print(f"Error: Input file {input_path} not found. Did you run ingestion first?")
        sys.exit(1)
        
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Read the raw Parquet file
    print("Reading raw data...")
    df = pd.read_parquet(input_path)
    initial_rows = len(df)
    print(f"Rows loaded: {initial_rows}")
    
    # 3. Add source tracking (Contract requirement)
    df['source_file'] = f"yellow_tripdata_{month}.parquet"
    df['source_row_number'] = df.index
    
    # 4. Rename columns to match contract (e.g., tpep_pickup_datetime -> pickup_datetime)
    df = df.rename(columns={
        'tpep_pickup_datetime': 'pickup_datetime',
        'tpep_dropoff_datetime': 'dropoff_datetime',
        'PULocationID': 'pickup_location_id',
        'DOLocationID': 'dropoff_location_id'
    })
    
    # 5. DATA QUALITY RULES (The core of Issue 2)
    # Rule A: Drop rows where pickup is after dropoff
    df = df[df['pickup_datetime'] < df['dropoff_datetime']]
    
    # Rule B: Trip distance must be >= 0
    df = df[df['trip_distance'] >= 0]
    
    # Rule C: Fare amount must be >= 0
    df = df[df['fare_amount'] >= 0]
    
    # Rule D: Total amount must be >= 0
    df = df[df['total_amount'] >= 0]
    
    # 6. Select only the columns specified in the contract
    columns_to_keep = [
        'pickup_datetime', 'dropoff_datetime', 'pickup_location_id', 
        'dropoff_location_id', 'trip_distance', 'passenger_count', 
        'fare_amount', 'total_amount', 'source_file', 'source_row_number'
    ]
    df = df[columns_to_keep]
    
    final_rows = len(df)
    rejected_rows = initial_rows - final_rows
    
    # 7. Save to a temporary file first (Atomic Move pattern from contract)
    temp_path = output_path + ".tmp"
    df.to_parquet(temp_path, index=False)
    
    # Rename temp file to final file (ensures no partial files)
    os.replace(temp_path, output_path)
    
    print(f"Validation complete!")
    print(f"Valid rows: {final_rows}")
    print(f"Rejected rows: {rejected_rows}")
    print(f"Saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate NYC Yellow Taxi Data")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format")
    args = parser.parse_args()
    
    validate_taxi_data(args.month)