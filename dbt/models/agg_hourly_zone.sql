-- depends_on: {{ source('gold', 'fact_trip') }}
SELECT data_month, pickup_hour, pickup_location_id AS location_id,
       count(*) AS trip_count, sum(total_amount) AS total_revenue,
       sum(fare_amount) AS total_fare, sum(trip_distance) AS total_distance,
       sum(duration_minutes) AS total_duration
FROM gold.fact_trip
GROUP BY data_month, pickup_hour, pickup_location_id
