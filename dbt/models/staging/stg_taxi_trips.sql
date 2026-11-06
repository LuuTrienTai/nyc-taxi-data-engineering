select
    data_month,
    trip_id,
    pickup_datetime,
    dropoff_datetime,
    pickup_datetime_utc,
    weather_hour_utc,
    pickup_location_id,
    dropoff_location_id,
    trip_distance,
    passenger_count,
    fare_amount,
    tip_amount,
    total_amount,
    vendor_id,
    payment_type_id,
    rate_code_id,
    source_file
from {{ source('raw_staging','taxi_trips') }}
where trip_id is not null
