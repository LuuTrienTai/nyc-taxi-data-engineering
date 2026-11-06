-- ==========================================
-- M4: Gold Layer Aggregation Definitions
-- ==========================================

-- GOLD 1: Hourly Demand Mart (For "Trips by Hour" chart)
-- Aggregates total trips and revenue for every hour of the month.
CREATE OR REPLACE VIEW marts.agg_hourly_demand AS
SELECT 
    DATE_TRUNC('hour', pickup_datetime) AS pickup_hour,
    COUNT(*) AS total_trips,
    SUM(total_amount) AS total_revenue,
    AVG(fare_amount) AS avg_fare
FROM staging.taxi_2026_01 -- (M3 will change this to point to the warehouse.fact_trip table)
GROUP BY 1;

-- GOLD 2: Zone Demand Mart (For "Top Pickup Zones" chart)
-- Aggregates total trips by pickup zone.
CREATE OR REPLACE VIEW marts.agg_zone_demand AS
SELECT 
    pickup_location_id,
    COUNT(*) AS total_trips,
    SUM(total_amount) AS total_revenue,
    AVG(trip_distance) AS avg_distance
FROM staging.taxi_2026_01
GROUP BY 1;

-- GOLD 3: Daily Demand Mart (For "Demand by Day" chart)
-- Aggregates total trips by day.
CREATE OR REPLACE VIEW marts.agg_daily_demand AS
SELECT 
    DATE_TRUNC('day', pickup_datetime) AS pickup_day,
    COUNT(*) AS total_trips,
    SUM(total_amount) AS total_revenue
FROM staging.taxi_2026_01
GROUP BY 1;