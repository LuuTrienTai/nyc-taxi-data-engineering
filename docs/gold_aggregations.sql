-- Preview Gold after dbt build. Definitions live in dbt/models/marts/.
SELECT * FROM marts.agg_hourly_demand WHERE data_month = DATE '2025-01-01' ORDER BY pickup_hour LIMIT 10;
SELECT * FROM marts.agg_daily_demand WHERE data_month = DATE '2025-01-01' ORDER BY pickup_day LIMIT 10;
SELECT * FROM marts.agg_zone_demand WHERE data_month = DATE '2025-01-01'
ORDER BY total_trips DESC, pickup_location_id LIMIT 10;
