-- 1. Total Trips KPI
SELECT COUNT(*) AS total_trips FROM warehouse.fact_trip WHERE data_month = '2025-01-01';

-- 2. Total Revenue KPI
SELECT SUM(total_amount) AS total_revenue FROM warehouse.fact_trip WHERE data_month = '2025-01-01';

-- 3. Average Fare KPI
SELECT AVG(fare_amount) AS avg_fare FROM warehouse.fact_trip WHERE data_month = '2025-01-01';

-- 4. Demand by Hour
SELECT EXTRACT(HOUR FROM pickup_datetime) AS pickup_hour, COUNT(*) AS trip_count
FROM warehouse.fact_trip WHERE data_month = '2025-01-01' GROUP BY pickup_hour ORDER BY pickup_hour;

-- 5. Top 10 Pickup Zones
SELECT pickup_location_id, COUNT(*) AS trip_count
FROM warehouse.fact_trip WHERE data_month = '2025-01-01' GROUP BY pickup_location_id ORDER BY trip_count DESC LIMIT 10;