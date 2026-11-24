SELECT data_month, run_id, status, rows_read, rows_loaded, rows_rejected, finished_at
FROM audit.pipeline_runs ORDER BY run_id DESC LIMIT 12;

SELECT q.run_id, q.reason, q.records
FROM quarantine.rejection_summary q JOIN audit.pipeline_runs a USING (run_id)
WHERE a.data_month = DATE '2025-01-01' ORDER BY q.run_id DESC, q.records DESC LIMIT 15;

SELECT inhrelid::regclass AS monthly_partition
FROM pg_inherits WHERE inhparent = 'gold.fact_trip'::regclass ORDER BY 1;

SELECT 'fact_trip' AS dataset, count(*) AS trips, sum(total_amount) AS charges
FROM gold.fact_trip WHERE data_month = DATE '2025-01-01'
UNION ALL
SELECT 'agg_hourly_zone', sum(trip_count), sum(total_revenue)
FROM gold.agg_hourly_zone WHERE data_month = DATE '2025-01-01'
UNION ALL
SELECT 'agg_daily_trips', sum(trip_count), sum(total_revenue)
FROM gold.agg_daily_trips WHERE data_month = DATE '2025-01-01'
UNION ALL
SELECT 'agg_zone_revenue', sum(trip_count), sum(total_revenue)
FROM gold.agg_zone_revenue WHERE data_month = DATE '2025-01-01';
