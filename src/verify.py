import argparse,json
import psycopg
from src.config import connection_kwargs
from src.ingestion.taxi import validate_month_arg

def verify_month(month):
    validate_month_arg(month);date=month+'-01'
    with psycopg.connect(**connection_kwargs()) as c:
        n,revenue=c.execute('SELECT count(*),coalesce(sum(total_amount),0) FROM gold.fact_trip WHERE data_month=%s',(date,)).fetchone()
        if n==0: raise AssertionError('Gold is empty')
        for table in ['agg_daily_demand','agg_zone_demand','agg_hourly_weather']:
            count,total=c.execute(f'SELECT coalesce(sum(trip_count),0),coalesce(sum(total_revenue),0) FROM gold.{table} WHERE data_month=%s',(date,)).fetchone()
            if count!=n or total!=revenue: raise AssertionError(f'{table}: count/revenue mismatch')
        run=c.execute("SELECT rows_read,rows_loaded,rows_rejected,run_id FROM audit.pipeline_runs WHERE data_month=%s AND status='success' ORDER BY run_id DESC LIMIT 1",(date,)).fetchone()
        if not run or run[0]!=run[1]+run[2] or run[1]!=n: raise AssertionError('Audit reconciliation failed')
        rejects=c.execute('SELECT count(*) FROM audit.rejections WHERE run_id=%s',(run[3],)).fetchone()[0]
        if rejects!=run[2]: raise AssertionError('Rejection lineage mismatch')
        absent=c.execute('SELECT count(*) FROM gold.fact_trip t LEFT JOIN gold.dim_weather_hour w ON t.pickup_hour=w.hour_local WHERE t.data_month=%s AND w.hour_local IS NULL',(date,)).fetchone()[0]
        if absent: raise AssertionError('Missing weather joins')
        forbidden=c.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('staging','silver')").fetchone()[0]
        if forbidden: raise AssertionError('Legacy staging/silver objects found; use clean project database')
        result={'month':month,'fact_rows':n,'revenue':str(revenue),'rejected':rejects,'checks':'PASS'}
        print(json.dumps(result));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--month',required=True);a=p.parse_args();verify_month(a.month)
