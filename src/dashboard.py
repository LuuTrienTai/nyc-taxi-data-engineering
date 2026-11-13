"""Local read-only dashboard. Use Metabase for ad-hoc questions."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from pathlib import Path
import psycopg
from src.config import BASE_DIR,connection_kwargs
from src.ingestion.taxi import validate_month_arg
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u=urlparse(self.path)
        try:
            if u.path=='/':
                body=(BASE_DIR/'dashboard/index.html').read_bytes();kind='text/html; charset=utf-8'
            elif u.path=='/api':
                month=parse_qs(u.query).get('month',['2025-01'])[0];validate_month_arg(month)
                with psycopg.connect(**connection_kwargs()) as c:
                    c.execute('SET TRANSACTION READ ONLY')
                    months=[str(r[0])[:7] for r in c.execute('SELECT DISTINCT data_month FROM gold.agg_daily_demand ORDER BY 1')]
                    date=month+'-01'
                    daily=c.execute('SELECT pickup_date,trip_count,total_revenue FROM gold.agg_daily_demand WHERE data_month=%s ORDER BY 1',(date,)).fetchall()
                    zones=c.execute('SELECT z.zone_name,z.borough,a.trip_count,a.total_revenue FROM gold.agg_zone_demand a JOIN gold.dim_zone z USING(location_id) WHERE data_month=%s ORDER BY trip_count DESC LIMIT 10',(date,)).fetchall()
                    weather=c.execute("SELECT CASE WHEN precipitation_mm>0 THEN 'Rain / snow' ELSE 'Dry' END,count(*),round(avg(trip_count),2) FROM gold.agg_hourly_weather WHERE data_month=%s GROUP BY 1",(date,)).fetchall()
                    kpi=c.execute('SELECT coalesce(sum(trip_count),0),coalesce(sum(total_revenue),0) FROM gold.agg_daily_demand WHERE data_month=%s',(date,)).fetchone()
                    body=json.dumps(dict(months=months,daily=daily,zones=zones,weather=weather,kpi=kpi),default=str).encode();kind='application/json'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        except Exception as exc:
            print(type(exc).__name__,str(exc),flush=True)
            self.send_error(503,'Data unavailable: run the pipeline and check service logs')
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8501),Handler).serve_forever()
