import urllib.request
import os
import sys

# NYC TLC provides the zone lookup as a CSV file
ZONE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"

def download_zones():
    print("Downloading Zone Lookup data...")
    
    output_dir = os.path.join("data", "bronze", "zones")
    output_path = os.path.join(output_dir, "taxi_zone_lookup.csv")
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        urllib.request.urlretrieve(ZONE_URL, output_path)
        print(f"Download successful! Saved to: {output_path}")
    except Exception as e:
        print(f"Error downloading file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_zones()