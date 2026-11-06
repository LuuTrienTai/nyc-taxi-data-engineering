select data_month, trip_id from {{ ref('fact_trip') }}
where pickup_datetime is null or dropoff_datetime is null
   or dropoff_datetime <= pickup_datetime
