-- No Silver/staging tables: expected 0 rows
SELECT table_schema,table_name FROM information_schema.tables
WHERE table_schema IN ('staging','silver');
-- Fact/marts and audit results
SELECT data_month,count(*),sum(total_amount) FROM gold.fact_trip GROUP BY 1;
SELECT * FROM audit.pipeline_runs ORDER BY run_id DESC LIMIT 10;
SELECT run_id,reason,count(*) FROM audit.rejections GROUP BY 1,2 ORDER BY 1 DESC;
-- Counts: values must match by month
SELECT f.data_month,f.n fact_count,a.n mart_count FROM
 (SELECT data_month,count(*) n FROM gold.fact_trip GROUP BY 1) f JOIN
 (SELECT data_month,sum(trip_count) n FROM gold.agg_daily_demand GROUP BY 1) a USING(data_month);
-- Freshness is pipeline execution time, distinct from dataset month
SELECT data_month,max(finished_at) last_success FROM audit.pipeline_runs WHERE status='success' GROUP BY 1;
-- Verify analyst can read but cannot write
SELECT has_table_privilege('metabase_reader','gold.fact_trip','SELECT') can_read,
 has_table_privilege('metabase_reader','gold.fact_trip','INSERT') can_insert;
