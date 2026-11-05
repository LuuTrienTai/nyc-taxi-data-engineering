select
  source_file,
  source_row_number,
  pickup_datetime,
  dropoff_datetime,
  pickup_location_id,
  dropoff_location_id,
  trip_distance,
  passenger_count,
  fare_amount,
  total_amount,
  date_trunc('hour', pickup_datetime) as pickup_hour_local,
  pickup_datetime::date as pickup_date
from {{ source('raw', 'taxi_trips') }}
where pickup_datetime is not null and dropoff_datetime is not null
