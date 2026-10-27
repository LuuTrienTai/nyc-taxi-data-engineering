import argparse
import urllib.request
import os
import sys

# The base URL where NYC TLC hosts the data
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"

def download_taxi_data(month: str):
    """
    Downloads the raw parquet file for a given month (YYYY-MM).
    Saves it to data/bronze/taxi/
    """
    # 1. Define paths
    filename = f"yellow_tripdata_{month}.parquet"
    output_dir = os.path.join("data", "bronze", "taxi")
    output_path = os.path.join(output_dir, filename)
    
    # 2. Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # 3. Construct URL
    url = BASE_URL.format(month=month)
    print(f"Downloading from: {url}")
    print(f"Saving to: {output_path}")
    
    # 4. Download the file
    try:
        urllib.request.urlretrieve(url, output_path)
        print("Download successful!")
    except Exception as e:
        print(f"Error downloading file: {e}")
        sys.exit(1) # Exit with a non-zero code on failure

if __name__ == "__main__":
    # Setup the command-line interface
    parser = argparse.ArgumentParser(description="Download NYC Yellow Taxi Data")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format (e.g., 2026-01)")
    args = parser.parse_args()
    
    download_taxi_data(args.month)