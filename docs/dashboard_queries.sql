-- Demand: Line chart
SELECT pickup_date, trip_count, total_revenue
FROM gold.agg_daily_demand ORDER BY pickup_date;
-- Pickup zones: bar chart (add a data_month filter in Metabase)
SELECT a.data_month,z.zone_name,z.borough,a.trip_count,a.total_revenue
FROM gold.agg_zone_demand a JOIN gold.dim_zone z USING(location_id)
ORDER BY a.trip_count DESC;
-- Average hourly demand with zero-trip hours included
SELECT data_month,CASE WHEN precipitation_mm>0 THEN 'Wet' ELSE 'Dry' END weather,
 count(*) hours,round(avg(trip_count),2) avg_trips_per_hour
FROM gold.agg_hourly_weather GROUP BY 1,2 ORDER BY 1,2;
