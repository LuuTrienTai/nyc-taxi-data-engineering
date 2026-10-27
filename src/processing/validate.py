import argparse
import pandas as pd
import os
import sys

def validate_taxi_data(month: str):
    print(f"Starting validation for month: {month}")
    
    input_path = os.path.join("data", "bronze", "taxi", f"yellow_tripdata_{month}.parquet")
    output_dir = os.path.join("data", "silver", "taxi")
    output_path = os.path.join(output_dir, f"taxi_{month}.parquet")
    
    quarantine_dir = os.path.join("data", "quarantine")
    quarantine_path = os.path.join(quarantine_dir, f"taxi_rejected_{month}.parquet")
    
    if not os.path.exists(input_path):
        print(f"Error: Input file {input_path} not found.")
        sys.exit(1)
        
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(quarantine_dir, exist_ok=True)
    
    print("Reading raw data...")
    df = pd.read_parquet(input_path)
    initial_rows = len(df)
    
    # Add tracking columns
    df['source_file'] = f"yellow_tripdata_{month}.parquet"
    df['source_row_number'] = df.index
    
    # Rename columns
    df = df.rename(columns={
        'tpep_pickup_datetime': 'pickup_datetime',
        'tpep_dropoff_datetime': 'dropoff_datetime',
        'PULocationID': 'pickup_location_id',
        'DOLocationID': 'dropoff_location_id'
    })
    
    # --- DATA QUALITY RULES ---
    # Create boolean masks for valid rows
    valid_time = df['pickup_datetime'] < df['dropoff_datetime']
    valid_distance = df['trip_distance'] >= 0
    valid_fare = df['fare_amount'] >= 0
    valid_total = df['total_amount'] >= 0
    
    # A row is valid only if ALL conditions are true
    all_valid = valid_time & valid_distance & valid_fare & valid_total
    
    # Split the data
    valid_df = df[all_valid].copy()
    rejected_df = df[~all_valid].copy()
    
    # Add a reason code to the rejected rows
    def get_reason(row):
        reasons = []
        if not (row['pickup_datetime'] < row['dropoff_datetime']): reasons.append("invalid_time")
        if row['trip_distance'] < 0: reasons.append("negative_distance")
        if row['fare_amount'] < 0: reasons.append("negative_fare")
        if row['total_amount'] < 0: reasons.append("negative_total")
        return ",".join(reasons)
        
    rejected_df['rejection_reason'] = rejected_df.apply(get_reason, axis=1)
    
    # Select only contract columns for Silver
    columns_to_keep = [
        'pickup_datetime', 'dropoff_datetime', 'pickup_location_id', 
        'dropoff_location_id', 'trip_distance', 'passenger_count', 
        'fare_amount', 'total_amount', 'source_file', 'source_row_number'
    ]
    valid_df = valid_df[columns_to_keep]
    
    # --- ATOMIC SAVES ---
    # Save Valid data
    temp_silver = output_path + ".tmp"
    valid_df.to_parquet(temp_silver, index=False)
    os.replace(temp_silver, output_path)
    
    # Save Quarantine data (if any)
    if len(rejected_df) > 0:
        temp_quarantine = quarantine_path + ".tmp"
        rejected_df.to_parquet(temp_quarantine, index=False)
        os.replace(temp_quarantine, quarantine_path)
        print(f"Quarantined {len(rejected_df)} rows to {quarantine_path}")
    
    print(f"Validation complete! Valid rows: {len(valid_df)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate NYC Yellow Taxi Data")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format")
    args = parser.parse_args()
    
    validate_taxi_data(args.month)