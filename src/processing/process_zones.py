import pandas as pd
import os

def process_zones():
    print("Processing Zone Lookup data...")
    
    input_path = os.path.join("data", "bronze", "zones", "taxi_zone_lookup.csv")
    output_dir = os.path.join("data", "silver", "zones")
    output_path = os.path.join(output_dir, "taxi_zone_lookup.parquet")
    
    os.makedirs(output_dir, exist_ok=True)
    
    df = pd.read_csv(input_path)
    
    # Rename columns to match standard naming
    df = df.rename(columns={
        'LocationID': 'location_id',
        'Borough': 'borough',
        'Zone': 'zone',
        'service_zone': 'service_zone'
    })
    
    # Save to Parquet
    temp_path = output_path + ".tmp"
    df.to_parquet(temp_path, index=False)
    os.replace(temp_path, output_path)
    
    print(f"Zones processed: {len(df)} rows saved to {output_path}")

if __name__ == "__main__":
    process_zones()