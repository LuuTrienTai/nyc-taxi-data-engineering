-- depends_on: {{ source('gold', 'fact_trip') }}
SELECT data_month, pickup_location_id AS location_id, count(*) AS trip_count,
       sum(total_amount) AS total_revenue, avg(fare_amount) AS avg_fare
FROM gold.fact_trip
GROUP BY data_month, pickup_location_id
