-- Demo month. Replace DATE '2025-01-01' with the first day of your loaded month.
SELECT sum(total_trips) AS total_trips, round(sum(total_revenue)::numeric, 2) AS total_revenue
FROM marts.agg_daily_demand WHERE data_month = DATE '2025-01-01';

SELECT avg(fare_amount) AS avg_fare
FROM warehouse.fact_trip WHERE data_month = DATE '2025-01-01';

SELECT pickup_day, total_trips
FROM marts.agg_daily_demand WHERE data_month = DATE '2025-01-01' ORDER BY pickup_day;

SELECT extract(hour FROM pickup_hour) AS hour_of_day, sum(total_trips) AS total_trips
FROM marts.agg_hourly_demand WHERE data_month = DATE '2025-01-01'
GROUP BY 1 ORDER BY 1;

SELECT pickup_location_id, pickup_zone_name, total_trips
FROM marts.agg_zone_demand WHERE data_month = DATE '2025-01-01'
ORDER BY total_trips DESC, pickup_location_id LIMIT 10;

SELECT extract(isodow FROM pickup_day) AS iso_weekday, sum(total_trips) AS total_trips
FROM marts.agg_daily_demand WHERE data_month = DATE '2025-01-01'
GROUP BY 1 ORDER BY 1;

SELECT weather_hour_utc, pickup_hour_local, total_trips, precipitation_mm, temperature_c
FROM marts.mart_hourly_weather WHERE data_month = DATE '2025-01-01' ORDER BY weather_hour_utc;
