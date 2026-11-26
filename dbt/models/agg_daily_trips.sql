-- depends_on: {{ source('gold', 'fact_trip') }}
SELECT data_month, pickup_date, count(*) AS trip_count,
       sum(total_amount) AS total_revenue, avg(trip_distance) AS avg_distance,
       avg(duration_minutes) AS avg_duration_minutes
FROM gold.fact_trip
GROUP BY data_month, pickup_date
