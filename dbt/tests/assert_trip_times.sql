select trip_key from {{ ref('fact_trip') }}
where dropoff_datetime < pickup_datetime
