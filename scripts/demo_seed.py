"""Generate a deterministic, clearly labeled offline dataset."""
import argparse

import pandas as pd

from src.config import DATA_DIR, BRONZE_TAXI_DIR, BRONZE_WEATHER_DIR, BRONZE_ZONES_DIR, bronze_lock
from src.ingestion.taxi import validate_month_arg


def seed(month):
    validate_month_arg(month)
    if DATA_DIR.name != 'demo':
        raise ValueError('Set DATA_DIR=/opt/project/data/demo')
    start = pd.Timestamp(month + '-01')
    end = start + pd.offsets.MonthBegin(1)
    rows = []
    for i in range(1200):
        day = (i * 13 // 30) % (end - start).days
        hour = [8, 9, 12, 16, 17, 18, 19, 22][i % 8]
        pickup = start + pd.Timedelta(days=day, hours=hour, seconds=i)
        distance = round(0.6 + ((i * 17) % 110) / 10, 2)
        fare = round(4.5 + 3.1 * distance, 2)
        tip = round(fare * (i % 4) * 0.06, 2)
        rows.append(dict(
            tpep_pickup_datetime=pickup, tpep_dropoff_datetime=pickup + pd.Timedelta(seconds=480 + round(distance * 180)),
            PULocationID=[1, 1, 2, 1, 3, 4, 2, 5][i % 8], DOLocationID=1 + (i + 1) % 5,
            trip_distance=distance, passenger_count=1 + i % 3, VendorID=1 + i % 2,
            fare_amount=fare, tip_amount=tip, total_amount=round(fare + tip + 3.5, 2), payment_type=1,
        ))
    rows.extend([dict(rows[0]), dict(rows[1], trip_distance=-1.), dict(rows[2], PULocationID=9999)])
    with bronze_lock():
        pd.DataFrame(rows).to_parquet(BRONZE_TAXI_DIR / f'yellow_tripdata_{month}.parquet', index=False)
        pd.DataFrame({
            'LocationID': [1, 2, 3, 4, 5],
            'Borough': ['Manhattan', 'Manhattan', 'Queens', 'Brooklyn', 'Queens'],
            'Zone': ['Midtown', 'Upper West Side', 'Long Island City', 'Downtown Brooklyn', 'Astoria'],
            'service_zone': ['Demo'] * 5,
        }).to_csv(BRONZE_ZONES_DIR / 'taxi_zone_lookup.csv', index=False)
        utc = pd.date_range(start, end + pd.Timedelta(days=1), freq='h', inclusive='left')
        pd.DataFrame({
            'observation_time_utc': utc.strftime('%Y-%m-%dT%H:%M'),
            'temperature_2m': [5. + i % 10 for i in range(len(utc))],
            'precipitation': [0.5 if i % 7 == 0 else 0 for i in range(len(utc))],
        }).to_parquet(BRONZE_WEATHER_DIR / f'weather_{month}.parquet', index=False)
    print('SYNTHETIC DEMO: 1,203 Bronze rows → 1,200 Gold rows + 3 Quarantine records')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', default='2025-01')
    seed(parser.parse_args().month)
