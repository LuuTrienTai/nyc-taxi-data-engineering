import psycopg
from src.config import connection_kwargs
with psycopg.connect(**connection_kwargs()) as c:
    for label,q in [('FACT','SELECT pickup_datetime::date,count(*),sum(total_amount) FROM gold.fact_trip GROUP BY 1'),('GOLD MART','SELECT pickup_date,trip_count,total_revenue FROM gold.agg_daily_demand')]:
        print('\n'+label)
        for r in c.execute('EXPLAIN (ANALYZE, BUFFERS) '+q): print(r[0])
