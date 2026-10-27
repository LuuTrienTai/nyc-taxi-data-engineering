import argparse
import pandas as pd
import json
import os
import sys

def process_weather(month: str):
    print(f"Processing weather data for {month}...")
    
    input_path = os.path.join("data", "bronze", "weather", f"weather_{month}.json")
    output_dir = os.path.join("data", "silver", "weather")
    output_path = os.path.join(output_dir, f"weather_{month}.parquet")
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        sys.exit(1)
        
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Read the JSON
    with open(input_path, 'r') as f:
        data = json.load(f)
        
    # 2. Extract the hourly arrays
    hourly = data['hourly']
    
    # 3. Create a DataFrame
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(hourly['time']),
        'temperature_2m': hourly['temperature_2m'],
        'precipitation': hourly['precipitation']
    })
    
    # Ensure timezone aware (Open-Meteo returns UTC or local based on request)
    # For our contract, we want consistent timezones.
    # We'll leave it as is for now, but this is where timezone alignment happens.
    
    # 4. Save to Parquet
    temp_path = output_path + ".tmp"
    df.to_parquet(temp_path, index=False)
    os.replace(temp_path, output_path)
    
    print(f"Weather processed: {len(df)} rows saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    args = parser.parse_args()
    process_weather(args.month)