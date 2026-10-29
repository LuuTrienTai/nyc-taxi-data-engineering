-- ==========================================
-- M4: Analytical KPIs & Dashboard Queries
-- ==========================================

-- 1. Total Trips KPI
SELECT COUNT(*) AS total_trips 
FROM staging.taxi_2026_01;

-- 2. Total Revenue KPI
SELECT SUM(total_amount) AS total_revenue 
FROM staging.taxi_2026_01;

-- 3. Average Fare KPI
SELECT AVG(fare_amount) AS avg_fare 
FROM staging.taxi_2026_01;

-- 4. Demand by Hour (For the "Trips by Hour" line chart)
SELECT 
    EXTRACT(HOUR FROM pickup_datetime) AS pickup_hour,
    COUNT(*) AS trip_count
FROM staging.taxi_2026_01
GROUP BY pickup_hour
ORDER BY pickup_hour;

-- 5. Top 10 Pickup Zones (For the "Most active zones" bar chart)
-- Note: In the future, M3 will JOIN this with the dim_zone table to get the actual Zone names.
SELECT 
    pickup_location_id,
    COUNT(*) AS trip_count
FROM staging.taxi_2026_01
GROUP BY pickup_location_id
ORDER BY trip_count DESC
LIMIT 10;

-- 6. Demand by Day of Week (For the "Weekday vs Weekend" chart)
SELECT 
    TO_CHAR(pickup_datetime, 'Day') AS day_of_week,
    COUNT(*) AS trip_count
FROM staging.taxi_2026_01
GROUP BY day_of_week
ORDER BY trip_count DESC;