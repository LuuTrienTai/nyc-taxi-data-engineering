-- 1. Total Trips KPI
SELECT COUNT(*) AS total_trips FROM staging.taxi_2026_01;

-- 2. Total Revenue KPI
SELECT SUM(total_amount) AS total_revenue FROM staging.taxi_2026_01;

-- 3. Average Fare KPI
SELECT AVG(fare_amount) AS avg_fare FROM staging.taxi_2026_01;

-- 4. Demand by Hour
SELECT EXTRACT(HOUR FROM pickup_datetime) AS pickup_hour, COUNT(*) AS trip_count
FROM staging.taxi_2026_01 GROUP BY pickup_hour ORDER BY pickup_hour;

-- 5. Top 10 Pickup Zones
SELECT pickup_location_id, COUNT(*) AS trip_count
FROM staging.taxi_2026_01 GROUP BY pickup_location_id ORDER BY trip_count DESC LIMIT 10;

-- 6. Demand by Day of Week
SELECT TO_CHAR(pickup_datetime, 'Day') AS day_of_week, COUNT(*) AS trip_count
FROM staging.taxi_2026_01 GROUP BY day_of_week ORDER BY trip_count DESC;