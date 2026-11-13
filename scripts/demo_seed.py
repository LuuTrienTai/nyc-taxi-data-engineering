"""Deterministic synthetic demo, isolated from real Bronze by DATA_DIR."""
import argparse
import pandas as pd
from src.config import DATA_DIR,BRONZE_TAXI_DIR,BRONZE_WEATHER_DIR,BRONZE_ZONES_DIR,ensure_directories
from src.ingestion.taxi import validate_month_arg

def seed(month):
    validate_month_arg(month)
    if DATA_DIR.name!='demo': raise RuntimeError('Set DATA_DIR=/opt/project/data/demo to avoid mixing demo and real data')
    ensure_directories();start=pd.Timestamp(month+'-01');end=start+pd.offsets.MonthBegin(1)
    rows=[]
    for i in range(1200):
        pickup=start+pd.Timedelta(hours=i%200,minutes=i%50)
        rows.append(dict(tpep_pickup_datetime=pickup,tpep_dropoff_datetime=pickup+pd.Timedelta(minutes=15),
          PULocationID=1+i%3,DOLocationID=1+(i+1)%3,trip_distance=2.5,passenger_count=1,
          fare_amount=12.,tip_amount=2.,total_amount=16.,payment_type=1))
    rows.append(dict(rows[0])) # distinct source row, same attributes: must remain
    rows.append(dict(rows[1],trip_distance=-1.))
    rows.append(dict(rows[2],PULocationID=9999))
    pd.DataFrame(rows).to_parquet(BRONZE_TAXI_DIR/f'yellow_tripdata_{month}.parquet',index=False)
    pd.DataFrame({'LocationID':[1,2,3],'Borough':['Manhattan','Queens','Brooklyn'],'Zone':['Demo A','Demo B','Demo C'],'service_zone':['Yellow']*3}).to_csv(BRONZE_ZONES_DIR/'taxi_zone_lookup.csv',index=False)
    utc=pd.date_range(start.tz_localize('UTC'),(end+pd.Timedelta(days=1)).tz_localize('UTC'),freq='h',inclusive='left')
    pd.DataFrame({'observation_time_utc':utc.strftime('%Y-%m-%dT%H:%M'),'temperature_2m':[5.+i%10 for i in range(len(utc))],'precipitation':[0.5 if i%7==0 else 0 for i in range(len(utc))]}).to_parquet(BRONZE_WEATHER_DIR/f'weather_{month}.parquet',index=False)
    print('SYNTHETIC DEMO: 1203 Bronze rows -> 1201 valid + 2 rejected; not real NYC results')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--month',default='2025-01');seed(p.parse_args().month)
