-- M3 Week 1: PostgreSQL staging contracts, aligned to M2 Silver Parquet.
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS staging.taxi_trips (
    trip_id TEXT NOT NULL,
    pickup_datetime TIMESTAMP,
    dropoff_datetime TIMESTAMP,
    pickup_datetime_utc TIMESTAMP,
    weather_hour_utc TIMESTAMP,
    observation_hour_ny TIMESTAMP,
    pickup_location_id INTEGER,
    dropoff_location_id INTEGER,
    trip_distance DOUBLE PRECISION,
    passenger_count INTEGER,
    fare_amount DOUBLE PRECISION,
    tip_amount DOUBLE PRECISION,
    total_amount DOUBLE PRECISION,
    vendor_id INTEGER,
    payment_type_id INTEGER,
    rate_code_id INTEGER,
    source_file TEXT,
    source_row_number BIGINT,
    data_month DATE NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (data_month, trip_id)
);
CREATE INDEX IF NOT EXISTS idx_staging_taxi_pickup ON staging.taxi_trips (pickup_datetime);
CREATE INDEX IF NOT EXISTS idx_staging_taxi_pickup_zone ON staging.taxi_trips (pickup_location_id);

CREATE TABLE IF NOT EXISTS staging.weather_hourly (
    observation_hour_utc TIMESTAMP NOT NULL,
    observation_hour_ny TIMESTAMP,
    temperature_c DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    rain_mm DOUBLE PRECISION,
    snowfall_cm DOUBLE PRECISION,
    wind_speed_kmh DOUBLE PRECISION,
    weather_code INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    source_file TEXT,
    source_row_number BIGINT,
    data_month DATE NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (data_month, observation_hour_utc)
);

CREATE TABLE IF NOT EXISTS staging.zones (
    location_id INTEGER PRIMARY KEY,
    borough TEXT,
    zone_name TEXT,
    service_zone TEXT,
    source_file TEXT,
    source_row_number BIGINT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit.monthly_loads (
    dataset TEXT NOT NULL,
    data_month DATE NOT NULL,
    source_file TEXT NOT NULL,
    rows_loaded BIGINT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset, data_month)
);
