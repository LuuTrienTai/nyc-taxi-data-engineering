"""Bronze → transient Silver → Gold, with one transaction per month."""
import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pyarrow.parquet as pq

from src.config import (
    BASE_DIR, BRONZE_TAXI_DIR, BRONZE_ZONES_DIR, BRONZE_WEATHER_DIR,
    BUSINESS_TIMEZONE, DATA_DIR, bronze_lock, connection_kwargs,
)
from src.ingestion.taxi import validate_month_arg, ingest_taxi_month, ingest_zones
from src.ingestion.weather import ingest_weather_month
from src.processing.silver import clean_batch
from src.quality import check_taxi_schema
from src.verify import MARTS, reconcile

IDENTITY_EXTRAS = (
    'VendorID', 'RatecodeID', 'payment_type', 'passenger_count', 'tip_amount',
    'extra', 'mta_tax', 'tolls_amount', 'improvement_surcharge',
    'congestion_surcharge', 'Airport_fee', 'cbd_congestion_fee',
)


def sha256(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def json_scalar(value):
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None if math.isnan(value) else str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def json_record(record):
    return {key: json_scalar(value) for key, value in record.items()}


def trip_digest(clean, extras):
    identity = (
        clean.pickup_datetime.isoformat(), clean.dropoff_datetime.isoformat(),
        int(clean.pickup_location_id), int(clean.dropoff_location_id),
        float(clean.trip_distance), float(clean.fare_amount), float(clean.total_amount),
        *extras,
    )
    return hashlib.md5(json.dumps(identity, separators=(',', ':')).encode(), usedforsecurity=False).digest()


def copy_frame(conn, table, frame):
    statement = sql.SQL('COPY {} ({}) FROM STDIN').format(
        sql.Identifier('gold', table), sql.SQL(', ').join(map(sql.Identifier, frame.columns)),
    )
    with conn.cursor().copy(statement) as copy:
        for row in frame.itertuples(index=False, name=None):
            copy.write_row(tuple(
                None if pd.isna(value) else value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
                for value in row
            ))


def prepare_dimensions(month):
    zones = pd.read_csv(BRONZE_ZONES_DIR / 'taxi_zone_lookup.csv', keep_default_na=False).rename(
        columns={'LocationID': 'location_id', 'Borough': 'borough', 'Zone': 'zone_name'}
    )
    zones = zones[['location_id', 'borough', 'zone_name', 'service_zone']]
    ids = pd.to_numeric(zones.location_id, errors='coerce')
    if (zones.empty or not ids.between(1, 2147483647).all() or not ids.mod(1).eq(0).all()
            or ids.duplicated().any() or zones[['borough', 'zone_name']].eq('').any().any()):
        raise ValueError('Invalid or duplicate zone dimension')
    zones['location_id'] = ids.astype(int)

    weather = pd.read_parquet(BRONZE_WEATHER_DIR / f'weather_{month}.parquet')
    utc = pd.to_datetime(weather.observation_time_utc, utc=True, errors='raise')
    if utc.isna().any() or utc.duplicated().any():
        raise ValueError('Invalid or duplicate weather UTC timestamps')
    weather['hour_local'] = utc.dt.tz_convert(BUSINESS_TIMEZONE).dt.tz_localize(None)
    start = pd.Timestamp(month + '-01')
    end = start + pd.offsets.MonthBegin(1)
    weather = weather[weather.hour_local.between(start, end, inclusive='left')]
    if (not weather.temperature_2m.between(-60, 60).all()
            or not weather.precipitation.between(0, 1000).all()):
        raise ValueError('Invalid weather values')
    expected = pd.date_range(
        start.tz_localize(BUSINESS_TIMEZONE), end.tz_localize(BUSINESS_TIMEZONE),
        freq='h', inclusive='left',
    ).tz_localize(None)
    if sorted(weather.hour_local) != sorted(expected):
        raise ValueError('Incomplete weather coverage: re-download Bronze weather with --force')
    # The repeated fall hour maps to one dimension row so the join never multiplies trips.
    weather = weather.groupby('hour_local', as_index=False).agg(
        temperature_c=('temperature_2m', 'mean'), precipitation_mm=('precipitation', 'mean'),
        observations=('hour_local', 'size'),
    )
    return zones, weather


def populate_dimensions(conn, start, end, zones, weather):
    conn.execute("""
        INSERT INTO gold.dim_date
        SELECT d, extract(year FROM d), extract(month FROM d), extract(day FROM d),
               extract(isodow FROM d), extract(isodow FROM d) >= 6
        FROM generate_series(%s::timestamp, %s::timestamp, interval '1 day') AS d
        ON CONFLICT DO NOTHING
    """, (start, end - timedelta(days=1)))
    with conn.cursor() as cursor:
        cursor.executemany("""
            INSERT INTO gold.dim_zone VALUES (%s,%s,%s,%s)
            ON CONFLICT (location_id) DO UPDATE SET borough=excluded.borough,
                zone_name=excluded.zone_name, service_zone=excluded.service_zone
        """, zones.itertuples(index=False, name=None))
        cursor.executemany("""
            INSERT INTO gold.dim_weather VALUES (%s,%s,%s,%s)
            ON CONFLICT (hour_local) DO UPDATE SET temperature_c=excluded.temperature_c,
                precipitation_mm=excluded.precipitation_mm, observations=excluded.observations
        """, weather.itertuples(index=False, name=None))


def prepare_gold_month(conn, start, end, zones, weather):
    populate_dimensions(conn, start, end, zones, weather)
    conn.execute(sql.SQL(
        'CREATE TABLE IF NOT EXISTS {} PARTITION OF gold.fact_trip FOR VALUES FROM ({}) TO ({})'
    ).format(sql.Identifier('gold', 'fact_trip_' + start.strftime('%Y_%m')), sql.Literal(start), sql.Literal(end)))
    conn.execute('DELETE FROM gold.fact_trip WHERE data_month = %s', (start,))


def process_trip_batches(conn, parquet, month, run_id, dimensions, batch_size, fail_after_batch):
    start, end, zones, weather = dimensions
    zone_labels = zones.set_index('location_id')[['borough', 'zone_name']].to_dict('index')
    weather_labels = weather.set_index('hour_local')[['temperature_c', 'precipitation_mm']].to_dict('index')
    read = loaded = rejected = 0
    seen = set()
    preview = []
    for batch in parquet.iter_batches(batch_size=batch_size):
        raw = batch.to_pandas()
        valid, invalid = clean_batch(raw, month, read, zone_labels.keys())
        reasons = dict(invalid.itertuples(index=False, name=None))
        # Normalize optional numeric attributes across Parquet integer/float types.
        extras = raw.reindex(columns=IDENTITY_EXTRAS).apply(pd.to_numeric, errors='coerce').astype(float)
        extras = extras.mask(extras.eq(0), 0.0)
        keys = []
        for clean, extra in zip(valid.itertuples(), extras.loc[valid.index].itertuples(index=False, name=None)):
            identity = trip_digest(clean, tuple(json_scalar(value) for value in extra))
            if identity in seen:
                reasons[clean.source_row] = 'duplicate_trip_id'
                keys.append(None)
            else:
                seen.add(identity)
                keys.append(identity.hex())
        valid = valid.assign(trip_id=keys).loc[lambda frame: frame.trip_id.notna()].copy()
        for name in ('pickup_location_id', 'dropoff_location_id', 'passenger_count', 'payment_type'):
            valid[name] = valid[name].astype('Int64')
        if not valid.empty:
            if loaded == 0:
                prepare_gold_month(conn, start, end, zones, weather)
            copy_frame(conn, 'fact_trip', valid)
        with conn.cursor().copy(
            'COPY quarantine.rejected_trip (run_id, source_row, reason, raw_record) FROM STDIN'
        ) as copy:
            for row, reason in reasons.items():
                record = raw.iloc[row - read - 1].to_dict()
                copy.write_row((run_id, row, reason, Jsonb(json_record(record))))
        for record in valid.head(max(0, 5 - len(preview))).to_dict('records'):
            pickup = zone_labels[record['pickup_location_id']]
            dropoff = zone_labels[record['dropoff_location_id']]
            enriched = dict(record, pickup_zone=pickup['zone_name'], pickup_borough=pickup['borough'],
                            dropoff_zone=dropoff['zone_name'], dropoff_borough=dropoff['borough'],
                            **weather_labels[record['pickup_hour']])
            preview.append({
                'bronze': json_record(raw.iloc[record['source_row'] - read - 1].to_dict()),
                'silver': json_record(enriched),
            })
        read += batch.num_rows
        loaded += len(valid)
        rejected += len(reasons)
        if fail_after_batch:
            raise RuntimeError('Injected failure after COPY')
    if read != loaded + rejected:
        raise ValueError('Silver row counts do not reconcile')
    return read, loaded, rejected, preview


def load_month(conn, run_id, month, batch_size, fail_after_batch):
    start = date.fromisoformat(month + '-01')
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    taxi = BRONZE_TAXI_DIR / f'yellow_tripdata_{month}.parquet'
    weather_path = BRONZE_WEATHER_DIR / f'weather_{month}.parquet'
    weather_raw = weather_path.with_suffix('.json')
    parquet = pq.ParquetFile(taxi)
    check_taxi_schema(parquet.schema_arrow.names)
    zones, weather = prepare_dimensions(month)
    files = [(taxi, 'NYC Yellow Taxi', parquet.metadata.num_rows),
             (BRONZE_ZONES_DIR / 'taxi_zone_lookup.csv', 'Taxi Zone Lookup', len(zones)),
             (weather_path, 'Hourly weather · Parquet', pq.read_metadata(weather_path).num_rows)]
    if weather_raw.exists():
        files.append((weather_raw, 'Open-Meteo · JSON', None))
    manifest = [
        dict(file=path.name, source=source, rows=rows, bytes=path.stat().st_size, sha256=sha256(path))
        for path, source, rows in files
    ]
    with conn.transaction():
        read, loaded, rejected, preview = process_trip_batches(
            conn, parquet, month, run_id, (start, end, zones, weather), batch_size, fail_after_batch,
        )
        if not loaded:
            conn.execute("""
                UPDATE audit.pipeline_runs SET status='failed', finished_at=clock_timestamp(),
                    error_message='No accepted trips; Gold was left intact',
                    rows_read=%s, rows_loaded=0, rows_rejected=%s, bronze_files=%s, preview='[]'::jsonb
                WHERE run_id=%s
            """, (read, rejected, Jsonb(manifest), run_id))
            return dict(run_id=run_id, month=month, bronze=read, gold=0, rejected=rejected)
        for table in MARTS:
            identifier = sql.Identifier('gold', table)
            model = (BASE_DIR / 'dbt' / 'models' / f'{table}.sql').read_text()
            conn.execute(sql.SQL('DELETE FROM {} WHERE data_month = %s').format(identifier), (start,))
            conn.execute(sql.SQL('INSERT INTO {} SELECT * FROM ({}) AS model WHERE data_month = %s')
                         .format(identifier, sql.SQL(model)), (start,))
        reconcile(conn, start, run_id, read, loaded, rejected)
        conn.execute("""
            UPDATE audit.pipeline_runs SET status='success', finished_at=clock_timestamp(),
                rows_read=%s, rows_loaded=%s, rows_rejected=%s, bronze_files=%s, preview=%s
            WHERE run_id=%s
        """, (read, loaded, rejected, Jsonb(manifest), Jsonb(preview), run_id))
    return dict(run_id=run_id, month=month, bronze=read, gold=loaded, rejected=rejected)


def build_gold(month, fail_after_batch=False, batch_size=50000):
    validate_month_arg(month)
    start = date.fromisoformat(month + '-01')
    source_kind = 'synthetic' if DATA_DIR.name == 'demo' else 'tlc'
    with bronze_lock(), psycopg.connect(**connection_kwargs(), autocommit=True) as conn:
        conn.execute((BASE_DIR / 'docker/postgres/init/01_gold.sql').read_text())
        conn.execute('SELECT pg_advisory_lock(746391)')
        # A previous worker may have exited before recording its failure.
        conn.execute("""
            UPDATE audit.pipeline_runs SET status='failed', finished_at=clock_timestamp(),
                error_message='Previous worker exited without completing the load'
            WHERE status='running'
        """)
        if conn.execute("""
            SELECT 1 FROM audit.pipeline_runs WHERE status='success' AND source_kind <> %s LIMIT 1
        """, (source_kind,)).fetchone():
            raise ValueError('Use separate databases for synthetic and real datasets')
        run_id = conn.execute("""
            INSERT INTO audit.pipeline_runs (data_month, status, source_kind)
            VALUES (%s, 'running', %s) RETURNING run_id
        """, (start, source_kind)).fetchone()[0]
        try:
            result = load_month(conn, run_id, month, batch_size, fail_after_batch)
        except Exception as exc:
            conn.execute("""
                UPDATE audit.pipeline_runs SET status='failed',finished_at=clock_timestamp(),error_message=%s
                WHERE run_id=%s
            """, (str(exc)[:2000], run_id))
            raise
    print(json.dumps(result))
    if not result['gold']:
        raise ValueError('No accepted trips; see Quarantine and run audit')
    return result


def ingest_month(month, force=False):
    validate_month_arg(month)
    if DATA_DIR.name == 'demo':
        raise ValueError('Use scripts.demo_seed with the synthetic DATA_DIR')
    with bronze_lock():
        ingest_zones(force)
        ingest_taxi_month(month, force)
        ingest_weather_month(month, force)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', required=True)
    parser.add_argument('--skip-download', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--fail-after-batch', action='store_true')
    args = parser.parse_args()
    if not args.skip_download:
        ingest_month(args.month, args.force)
    build_gold(args.month, args.fail_after_batch)


if __name__ == '__main__':
    main()
