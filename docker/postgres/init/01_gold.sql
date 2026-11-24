CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS quarantine;

CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_key date PRIMARY KEY,
    year smallint NOT NULL,
    month smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
    day_of_month smallint NOT NULL,
    iso_weekday smallint NOT NULL CHECK (iso_weekday BETWEEN 1 AND 7),
    is_weekend boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS gold.dim_zone (
    location_id integer PRIMARY KEY,
    borough text NOT NULL,
    zone_name text NOT NULL,
    service_zone text
);
CREATE TABLE IF NOT EXISTS gold.dim_weather (
    hour_local timestamp PRIMARY KEY,
    temperature_c double precision NOT NULL,
    precipitation_mm double precision NOT NULL CHECK (precipitation_mm >= 0),
    observations integer NOT NULL CHECK (observations BETWEEN 1 AND 2)
);
CREATE TABLE IF NOT EXISTS gold.fact_trip (
    data_month date NOT NULL,
    trip_id text NOT NULL CHECK (trip_id ~ '^[0-9a-f]{32}$'),
    source_row bigint NOT NULL,
    pickup_date date NOT NULL REFERENCES gold.dim_date,
    pickup_datetime timestamp NOT NULL,
    dropoff_datetime timestamp NOT NULL,
    pickup_hour timestamp NOT NULL REFERENCES gold.dim_weather,
    pickup_location_id integer NOT NULL REFERENCES gold.dim_zone,
    dropoff_location_id integer NOT NULL REFERENCES gold.dim_zone,
    passenger_count integer,
    trip_distance double precision NOT NULL CHECK (trip_distance > 0),
    fare_amount numeric(14,2) NOT NULL CHECK (fare_amount > 0),
    tip_amount numeric(14,2),
    total_amount numeric(14,2) NOT NULL CHECK (total_amount > 0),
    duration_minutes double precision NOT NULL CHECK (duration_minutes > 0),
    payment_type integer,
    dst_ambiguous boolean NOT NULL,
    PRIMARY KEY (data_month, trip_id),
    UNIQUE (data_month, source_row),
    CHECK (pickup_date = pickup_datetime::date),
    CHECK (pickup_hour = date_trunc('hour', pickup_datetime)),
    CHECK (data_month = date_trunc('month', pickup_datetime)::date)
) PARTITION BY RANGE (data_month);
CREATE INDEX IF NOT EXISTS fact_pickup_hour ON gold.fact_trip (pickup_hour);
CREATE INDEX IF NOT EXISTS fact_pickup_zone_hour ON gold.fact_trip (pickup_location_id, pickup_hour);

CREATE TABLE IF NOT EXISTS gold.agg_hourly_zone (
    data_month date NOT NULL,
    pickup_hour timestamp NOT NULL REFERENCES gold.dim_weather,
    location_id integer NOT NULL REFERENCES gold.dim_zone,
    trip_count bigint NOT NULL,
    total_revenue numeric NOT NULL,
    total_fare numeric NOT NULL,
    total_distance double precision NOT NULL,
    total_duration double precision NOT NULL,
    PRIMARY KEY (data_month, pickup_hour, location_id)
);
ALTER TABLE gold.agg_hourly_zone
    ADD COLUMN IF NOT EXISTS total_duration double precision NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS gold.agg_daily_trips (
    data_month date NOT NULL,
    pickup_date date NOT NULL REFERENCES gold.dim_date,
    trip_count bigint NOT NULL,
    total_revenue numeric NOT NULL,
    avg_distance double precision NOT NULL,
    avg_duration_minutes double precision NOT NULL,
    PRIMARY KEY (data_month, pickup_date)
);
CREATE TABLE IF NOT EXISTS gold.agg_zone_revenue (
    data_month date NOT NULL,
    location_id integer NOT NULL REFERENCES gold.dim_zone,
    trip_count bigint NOT NULL,
    total_revenue numeric NOT NULL,
    avg_fare numeric NOT NULL,
    PRIMARY KEY (data_month, location_id)
);
CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_month date NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('running','success','failed')),
    source_kind text NOT NULL CHECK (source_kind IN ('tlc','synthetic')),
    rows_read bigint,
    rows_loaded bigint,
    rows_rejected bigint,
    bronze_files jsonb,
    preview jsonb,
    error_message text,
    CHECK (status <> 'success' OR (
        rows_read IS NOT NULL AND rows_loaded > 0 AND rows_rejected >= 0
        AND rows_read = rows_loaded + rows_rejected AND finished_at IS NOT NULL
    ))
);
CREATE INDEX IF NOT EXISTS audit_runs_month ON audit.pipeline_runs (data_month, run_id DESC);

CREATE TABLE IF NOT EXISTS quarantine.rejected_trip (
    run_id bigint NOT NULL REFERENCES audit.pipeline_runs,
    source_row bigint NOT NULL,
    reason text NOT NULL,
    raw_record jsonb NOT NULL,
    PRIMARY KEY (run_id, source_row)
);
CREATE OR REPLACE VIEW quarantine.rejection_summary AS
SELECT run_id, reason, count(*) AS records
FROM quarantine.rejected_trip
GROUP BY run_id, reason;
