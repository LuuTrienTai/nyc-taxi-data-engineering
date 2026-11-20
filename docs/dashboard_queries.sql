-- ==========================================
-- M4 Metabase Questions (Source: gold schema)
-- ==========================================

-- 1. KPI: Total Valid Trips
SELECT COUNT(*) AS total_trips 
FROM gold.fact_trip 
WHERE data_month = '2025-01-01';

-- 2. KPI: Total Revenue
SELECT SUM(total_amount) AS total_revenue 
FROM gold.fact_trip 
WHERE data_month = '2025-01-01';

-- 3. Chart: Daily Pickup Demand (Line/Bar chart)
-- In Metabase: X-axis = pickup_date, Y-axis = trip_count
SELECT pickup_date, trip_count, total_revenue
FROM gold.agg_daily_demand 
WHERE data_month = '2025-01-01' 
ORDER BY pickup_date;

-- 4. Chart: Top 10 Pickup Zones (Bar chart)
-- In Metabase: X-axis = zone_name, Y-axis = trip_count
SELECT z.zone_name, z.borough, a.trip_count, a.total_revenue
FROM gold.agg_zone_demand a
JOIN gold.dim_zone z USING(location_id)
WHERE a.data_month = '2025-01-01'
ORDER BY a.trip_count DESC 
LIMIT 10;

-- 5. Chart: Weather & Hourly Demand (Table)
SELECT 
    CASE WHEN precipitation_mm > 0 THEN 'Rain / snow' ELSE 'Dry' END AS condition,
    COUNT(*) AS hours,
    ROUND(AVG(trip_count), 2) AS avg_trips_per_hour
FROM gold.agg_hourly_weather 
WHERE data_month = '2025-01-01' 
GROUP BY 1;