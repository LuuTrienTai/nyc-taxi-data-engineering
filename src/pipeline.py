"""Bronze -> transient Silver -> Gold, one atomic transaction per month."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
import psycopg
from src.config import BASE_DIR, BRONZE_TAXI_DIR, BRONZE_ZONES_DIR, BRONZE_WEATHER_DIR, connection_kwargs, ensure_directories
from src.ingestion.taxi import validate_month_arg, ingest_taxi_month, ingest_zones
from src.ingestion.weather import ingest_weather_month
from src.processing.silver import clean_batch, COLUMNS
import pyarrow.parquet as pq

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def copy_frame(conn, table, frame):
    from psycopg import sql
    stmt=sql.SQL('COPY {} ({}) FROM STDIN').format(sql.Identifier('gold',table),sql.SQL(',').join(map(sql.Identifier,frame.columns)))
    with conn.cursor().copy(stmt) as cp:
        for row in frame.itertuples(index=False,name=None):
            cp.write_row(tuple(None if pd.isna(v) else v.to_pydatetime() if isinstance(v,pd.Timestamp) else v for v in row))
def prepare_dimensions(month):
    z=pd.read_csv(BRONZE_ZONES_DIR/'taxi_zone_lookup.csv',keep_default_na=False).rename(columns={'LocationID':'location_id','Borough':'borough','Zone':'zone_name'})
    z=z[['location_id','borough','zone_name','service_zone']]
    if z.location_id.isna().any() or z.location_id.duplicated().any() or z[['borough','zone_name']].isna().any().any():
        raise ValueError('Invalid or duplicate zone dimension')
    w=pd.read_parquet(BRONZE_WEATHER_DIR/f'weather_{month}.parquet')
    utc=pd.to_datetime(w.observation_time_utc,utc=True,errors='raise')
    if utc.duplicated().any(): raise ValueError('Duplicate weather UTC timestamps')
    w['hour_local']=utc.dt.tz_convert('America/New_York').dt.tz_localize(None)
    start=pd.Timestamp(month+'-01');end=start+pd.offsets.MonthBegin(1)
    w=w[(w.hour_local>=start)&(w.hour_local<end)].copy()
    if w.empty or w[['temperature_2m','precipitation']].isna().any().any() or not w.temperature_2m.between(-60,60).all() or not w.precipitation.ge(0).all():
        raise ValueError('Invalid weather data')
    expected=pd.date_range(start.tz_localize('America/New_York'),end.tz_localize('America/New_York'),freq='h',inclusive='left').tz_localize(None)
    if set(w.hour_local)!=set(expected): raise ValueError('Incomplete weather coverage: re-download Bronze weather with --force')
    # Repeated local DST hour is averaged, not joined twice.
    w=w.groupby('hour_local',as_index=False).agg(temperature_c=('temperature_2m','mean'),precipitation_mm=('precipitation','mean'),observations=('hour_local','size'))
    return z,w

def build_gold(month, fail_after_batch=False, batch_size=50000):
    validate_month_arg(month)
    month_date=pd.Timestamp(month+'-01').date()
    path=BRONZE_TAXI_DIR/f'yellow_tripdata_{month}.parquet'
    with psycopg.connect(**connection_kwargs(),autocommit=True) as conn:
        conn.execute((BASE_DIR/'docker/postgres/init/01_gold.sql').read_text())
        # Serialize writers including shared dimensions; held through commit and released on disconnect.
        conn.execute('SELECT pg_advisory_lock(746391)')
        run_id=conn.execute("INSERT INTO audit.pipeline_runs(data_month,status) VALUES (%s,'running') RETURNING run_id",(month_date,)).fetchone()[0]
        try:
            fingerprint=sha256(path)
            zones,weather=prepare_dimensions(month)
            read=loaded=rejected=0
            with conn.transaction():
                for r in zones.itertuples(index=False,name=None):
                    conn.execute('INSERT INTO gold.dim_zone VALUES (%s,%s,%s,%s) ON CONFLICT(location_id) DO UPDATE SET borough=EXCLUDED.borough,zone_name=EXCLUDED.zone_name,service_zone=EXCLUDED.service_zone',tuple(None if pd.isna(v) else v for v in r))
                for r in weather.itertuples(index=False,name=None):
                    conn.execute('INSERT INTO gold.dim_weather_hour VALUES (%s,%s,%s,%s) ON CONFLICT(hour_local) DO UPDATE SET temperature_c=EXCLUDED.temperature_c,precipitation_mm=EXCLUDED.precipitation_mm,observations=EXCLUDED.observations',r)
                for table in ['agg_daily_demand','agg_zone_demand','agg_hourly_weather','fact_trip']:
                    conn.execute(f'DELETE FROM gold.{table} WHERE data_month=%s',(month_date,))
                for batch in pq.ParquetFile(path).iter_batches(batch_size=batch_size):
                    valid,bad=clean_batch(batch.to_pandas(),month,read,set(zones.location_id))
                    read+=batch.num_rows;loaded+=len(valid);rejected+=len(bad)
                    integer_columns = [
                        "passenger_count",
                        "payment_type",
                        "VendorID",
                        "RatecodeID",
                        "PULocationID",
                        "DOLocationID",
                    ]

                    for column in integer_columns:
                        if column in valid.columns:
                            valid[column] = valid[column].astype("Int64")
                    copy_frame(conn,'fact_trip',valid)
                    with conn.cursor().copy('COPY audit.rejections(run_id,source_row,reason) FROM STDIN') as cp:
                        for row,reason in bad.itertuples(index=False,name=None): cp.write_row((run_id,row,reason))
                    if fail_after_batch: raise RuntimeError('Injected failure after COPY: rollback demonstration')
                if not loaded or read!=loaded+rejected: raise ValueError('Empty Gold or failed row reconciliation')
                conn.execute("""INSERT INTO gold.agg_daily_demand SELECT data_month,pickup_datetime::date,count(*),sum(total_amount),avg(trip_distance),avg(duration_minutes) FROM gold.fact_trip WHERE data_month=%s GROUP BY 1,2""",(month_date,))
                conn.execute("""INSERT INTO gold.agg_zone_demand SELECT data_month,pickup_location_id,count(*),sum(total_amount) FROM gold.fact_trip WHERE data_month=%s GROUP BY 1,2""",(month_date,))
                conn.execute("""INSERT INTO gold.agg_hourly_weather
                  SELECT %s,w.hour_local,count(t.source_row),coalesce(sum(t.total_amount),0),w.temperature_c,w.precipitation_mm
                  FROM gold.dim_weather_hour w LEFT JOIN gold.fact_trip t ON t.pickup_hour=w.hour_local AND t.data_month=%s
                  WHERE w.hour_local >= %s::date AND w.hour_local < %s::date + interval '1 month'
                  GROUP BY w.hour_local,w.temperature_c,w.precipitation_mm""",(month_date,month_date,month_date,month_date))
                conn.execute("UPDATE audit.pipeline_runs SET status='success',finished_at=now(),rows_read=%s,rows_loaded=%s,rows_rejected=%s,source_sha256=%s WHERE run_id=%s",(read,loaded,rejected,fingerprint,run_id))
            result=dict(run_id=run_id,month=month,bronze=read,gold=loaded,rejected=rejected)
            print(json.dumps(result));return result
        except Exception as exc:
            conn.execute("UPDATE audit.pipeline_runs SET status='failed',finished_at=now(),error_message=%s WHERE run_id=%s",(str(exc)[:2000],run_id))
            raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--month',required=True)
    p.add_argument('--skip-download',action='store_true');p.add_argument('--force',action='store_true')
    p.add_argument('--fail-after-batch',action='store_true');a=p.parse_args()
    validate_month_arg(a.month);ensure_directories()
    if not a.skip_download:
        ingest_zones(a.force);ingest_taxi_month(a.month,a.force);ingest_weather_month(a.month,a.force)
    build_gold(a.month,a.fail_after_batch)
if __name__=='__main__': main()
