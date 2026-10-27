import argparse
import urllib.request
import json
import os
import sys
import pandas as pd

# Coordinates for New York City
LAT = 40.7128
LON = -74.0060

def download_weather(month: str):
    print(f"Downloading Weather data for {month}...")
    
    # Calculate start and end dates for the month
    year, m = month.split("-")
    start_date = f"{year}-{m}-01"
    if m == "12":
        end_date = f"{int(year)+1}-01-01"
    else:
        end_date = f"{year}-{int(m)+1:02d}-01"
        
    # Open-Meteo Historical Weather API
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={LAT}&longitude={LON}&start_date={start_date}&end_date={end_date}&hourly=temperature_2m,precipitation"
    
    output_dir = os.path.join("data", "bronze", "weather")
    output_path = os.path.join(output_dir, f"weather_{month}.json")
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        with open(output_path, "w") as f:
            json.dump(data, f)
            
        print(f"Download successful! Saved to: {output_path}")
    except Exception as e:
        print(f"Error downloading weather: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Weather Data")
    parser.add_argument("--month", required=True, help="Month in YYYY-MM format")
    args = parser.parse_args()
    download_weather(args.month)