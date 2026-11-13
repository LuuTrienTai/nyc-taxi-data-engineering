CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE IF NOT EXISTS gold.dim_zone (
 location_id integer PRIMARY KEY, borough text NOT NULL, zone_name text NOT NULL, service_zone text);
CREATE TABLE IF NOT EXISTS gold.dim_weather_hour (
 hour_local timestamp PRIMARY KEY, temperature_c double precision, precipitation_mm double precision,
 observations integer NOT NULL);
CREATE TABLE IF NOT EXISTS gold.fact_trip (
 data_month date NOT NULL, source_row bigint NOT NULL,
 pickup_datetime timestamp NOT NULL, dropoff_datetime timestamp NOT NULL, pickup_hour timestamp NOT NULL,
 pickup_location_id integer REFERENCES gold.dim_zone, dropoff_location_id integer REFERENCES gold.dim_zone,
 passenger_count integer, trip_distance double precision CHECK(trip_distance>0),
 fare_amount numeric(14,2), tip_amount numeric(14,2), total_amount numeric(14,2),
 duration_minutes double precision CHECK(duration_minutes>0), payment_type integer,
 dst_ambiguous boolean NOT NULL, PRIMARY KEY(data_month,source_row));
CREATE INDEX IF NOT EXISTS fact_pickup_time ON gold.fact_trip(pickup_datetime);
CREATE INDEX IF NOT EXISTS fact_pickup_zone ON gold.fact_trip(pickup_location_id);
CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
 run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, data_month date NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
 status text NOT NULL CHECK(status IN ('running','success','failed')),
 rows_read bigint, rows_loaded bigint, rows_rejected bigint, source_sha256 text,
 error_message text);
CREATE TABLE IF NOT EXISTS audit.rejections (
 run_id bigint REFERENCES audit.pipeline_runs, source_row bigint, reason text,
 PRIMARY KEY(run_id,source_row));
CREATE TABLE IF NOT EXISTS gold.agg_daily_demand (
 data_month date, pickup_date date, trip_count bigint, total_revenue numeric,
 avg_distance double precision, avg_duration_minutes double precision,
 PRIMARY KEY(data_month,pickup_date));
CREATE TABLE IF NOT EXISTS gold.agg_zone_demand (
 data_month date, location_id integer REFERENCES gold.dim_zone, trip_count bigint,
 total_revenue numeric, PRIMARY KEY(data_month,location_id));
CREATE TABLE IF NOT EXISTS gold.agg_hourly_weather (
 data_month date, hour_local timestamp, trip_count bigint, total_revenue numeric,
 temperature_c double precision, precipitation_mm double precision,
 PRIMARY KEY(data_month,hour_local));
