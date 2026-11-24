-- Demand by pickup hour and borough
SELECT extract(hour FROM a.pickup_hour) AS pickup_hour, z.borough,
       sum(a.trip_count) AS trips, sum(a.total_revenue) AS total_charges
FROM gold.agg_hourly_zone a JOIN gold.dim_zone z USING (location_id)
WHERE a.data_month = DATE '2025-01-01'
GROUP BY 1, 2 ORDER BY 1, 2;

-- Weekday pattern using the calendar dimension
SELECT d.iso_weekday, sum(a.trip_count) AS trips, sum(a.total_revenue) AS total_charges
FROM gold.agg_daily_trips a JOIN gold.dim_date d ON d.date_key = a.pickup_date
WHERE a.data_month = DATE '2025-01-01'
GROUP BY 1 ORDER BY 1;

-- Weather demand with zero-trip hours included
WITH demand AS (
    SELECT pickup_hour, sum(trip_count) AS trips
    FROM gold.agg_hourly_zone WHERE data_month = DATE '2025-01-01' GROUP BY 1
)
SELECT w.precipitation_mm > 0 AS wet, count(*) AS local_hours, avg(coalesce(d.trips, 0)) AS trips_per_hour
FROM gold.dim_weather w LEFT JOIN demand d ON d.pickup_hour = w.hour_local
WHERE w.hour_local >= '2025-01-01' AND w.hour_local < '2025-02-01'
GROUP BY 1 ORDER BY 1;
