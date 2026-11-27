"""Local read-only dashboard and JSON API for the NYC Taxi warehouse."""
import json
import logging
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import psycopg
from psycopg.rows import dict_row
from psycopg import sql

from src.config import BASE_DIR, connection_kwargs
from src.ingestion.taxi import validate_month_arg

ASSETS = {
    '/': ('index.html', 'text/html'),
    '/styles.css': ('styles.css', 'text/css'),
    '/app.js': ('app.js', 'text/javascript'),
}
API_ROUTES = {'/api/catalog', '/api/analytics', '/api/distance', '/api/pipeline', '/api/gold'}
DATASETS = {
    'fact_trip': """
        SELECT t.trip_id, t.source_row, t.pickup_datetime, t.dropoff_datetime,
               pu.zone_name AS pickup_zone, dof.zone_name AS dropoff_zone,
               d.iso_weekday, w.temperature_c, w.precipitation_mm, t.trip_distance,
               t.fare_amount, t.total_amount, t.duration_minutes
        FROM (SELECT * FROM gold.fact_trip WHERE data_month=%s
              ORDER BY source_row LIMIT 25 OFFSET %s) t
        JOIN gold.dim_zone pu ON pu.location_id=t.pickup_location_id
        JOIN gold.dim_zone dof ON dof.location_id=t.dropoff_location_id
        JOIN gold.dim_date d ON d.date_key=t.pickup_date
        JOIN gold.dim_weather w ON w.hour_local=t.pickup_hour
        ORDER BY t.source_row
    """,
    'dim_date': 'SELECT * FROM gold.dim_date WHERE date_key >= %s AND date_key < %s ORDER BY date_key LIMIT 25 OFFSET %s',
    'dim_zone': 'SELECT * FROM gold.dim_zone ORDER BY location_id LIMIT 25 OFFSET %s',
    'dim_weather': 'SELECT * FROM gold.dim_weather WHERE hour_local >= %s AND hour_local < %s ORDER BY hour_local LIMIT 25 OFFSET %s',
    'agg_hourly_zone': 'SELECT * FROM gold.agg_hourly_zone WHERE data_month=%s ORDER BY pickup_hour, location_id LIMIT 25 OFFSET %s',
    'agg_daily_trips': 'SELECT * FROM gold.agg_daily_trips WHERE data_month=%s ORDER BY pickup_date LIMIT 25 OFFSET %s',
    'agg_zone_revenue': 'SELECT * FROM gold.agg_zone_revenue WHERE data_month=%s ORDER BY total_revenue DESC, location_id LIMIT 25 OFFSET %s',
}
DATASET_COUNTS = {
    'fact_trip': 'SELECT count(*) AS total FROM gold.fact_trip WHERE data_month=%s',
    'dim_date': 'SELECT count(*) AS total FROM gold.dim_date WHERE date_key >= %s AND date_key < %s',
    'dim_zone': 'SELECT count(*) AS total FROM gold.dim_zone',
    'dim_weather': 'SELECT count(*) AS total FROM gold.dim_weather WHERE hour_local >= %s AND hour_local < %s',
    'agg_hourly_zone': 'SELECT count(*) AS total FROM gold.agg_hourly_zone WHERE data_month=%s',
    'agg_daily_trips': 'SELECT count(*) AS total FROM gold.agg_daily_trips WHERE data_month=%s',
    'agg_zone_revenue': 'SELECT count(*) AS total FROM gold.agg_zone_revenue WHERE data_month=%s',
}


def summarize_weather_groups(hourly):
    groups = {}
    for row in hourly:
        temperature = float(row['temperature_c'])
        lower = int(temperature // 5) * 5
        group = groups.setdefault(lower, {
            'temperature_band': f'{lower} to under {lower + 5} °C',
            'hours': 0,
            'trips': 0,
            'precipitation': 0.0,
        })
        group['hours'] += 1
        group['trips'] += int(row['trips'])
        group['precipitation'] += float(row['precipitation_mm'])
    return [
        dict(
            **group,
            trips_per_hour=group['trips'] / group['hours'],
            average_precipitation=group['precipitation'] / group['hours'],
        )
        for _, group in sorted(groups.items(), key=lambda item: item[0])
    ]


def catalog(conn):
    return dict(
        months=conn.execute("""
            SELECT data_month, bool_or(status='success') AS has_gold,
                   coalesce(min(source_kind) FILTER (WHERE status='success'), min(source_kind)) AS source_kind,
                   to_char(data_month, 'YYYY-MM') AS month
            FROM audit.pipeline_runs GROUP BY data_month ORDER BY data_month DESC
        """).fetchall(),
        zones=conn.execute('SELECT location_id, borough, zone_name FROM gold.dim_zone ORDER BY borough, zone_name').fetchall(),
    )


def analytics(conn, start, end, param, distance_only=False):
    borough = param('borough', '') or None
    zone_value = param('zone', '')
    zone = int(zone_value) if zone_value else None
    role = param('location_role', 'pickup')
    if role not in ('pickup', 'dropoff'):
        raise ValueError('Invalid location role')
    location_column = {'pickup': 'pickup_location_id', 'dropoff': 'dropoff_location_id'}[role]
    date_from = date.fromisoformat(param('date_from', start.isoformat()))
    date_to = date.fromisoformat(param('date_to', (end - timedelta(days=1)).isoformat()))
    if not start <= date_from <= date_to < end:
        raise ValueError('Date range is outside the selected month')
    weather = param('weather', 'all')
    if weather not in ('all', 'wet', 'dry'):
        raise ValueError('Invalid weather filter')
    hour_value = param('hour', '')
    hour = int(hour_value) if hour_value else None
    if hour is not None and not 0 <= hour <= 23:
        raise ValueError('Invalid hour filter')
    args = dict(start=start, end=end, date_from=date_from, date_to=date_to,
                borough=borough, zone=zone, weather=weather, hour=hour)
    zone_filter = """
        AND (%(borough)s::text IS NULL OR z.borough=%(borough)s)
        AND (%(zone)s::integer IS NULL OR z.location_id=%(zone)s)
    """
    weather_filter = """
        AND (%(hour)s::integer IS NULL OR extract(hour FROM w.hour_local)=%(hour)s)
        AND (%(weather)s='all' OR (w.precipitation_mm>0)=(%(weather)s='wet'))
    """
    if distance_only:
        return conn.execute(sql.SQL("""
            SELECT width_bucket(t.trip_distance, ARRAY[0,1,3,5,10,20]) AS band,
                   count(*) AS trips,
                   avg(t.fare_amount) AS average_fare,
                   avg(t.total_amount) AS average_total,
                   avg(t.trip_distance) AS average_distance,
                   avg(t.duration_minutes) AS average_duration,
                   sum(t.fare_amount) / nullif(sum(t.trip_distance), 0) AS fare_per_mile
            FROM gold.fact_trip t
            JOIN gold.dim_zone z ON z.location_id=t.{location}
            JOIN gold.dim_weather w ON w.hour_local=t.pickup_hour
            WHERE t.data_month=%(start)s AND t.pickup_date BETWEEN %(date_from)s AND %(date_to)s
        """).format(location=sql.Identifier(location_column)) +
            sql.SQL(zone_filter + weather_filter + ' GROUP BY 1 ORDER BY 1'), args).fetchall()

    if role == 'pickup':
        demand_source = """
            SELECT a.pickup_hour AS hour_local, sum(a.trip_count) AS trips,
                   sum(a.total_revenue) AS revenue, sum(a.total_fare) AS fares,
                   sum(a.total_distance) AS distance, sum(a.total_duration) AS duration
            FROM gold.agg_hourly_zone a JOIN gold.dim_zone z USING (location_id)
            WHERE a.data_month=%(start)s AND a.pickup_hour::date BETWEEN %(date_from)s AND %(date_to)s
        """
    else:
        demand_source = """
            SELECT t.pickup_hour AS hour_local, count(*) AS trips,
                   sum(t.total_amount) AS revenue, sum(t.fare_amount) AS fares,
                   sum(t.trip_distance) AS distance, sum(t.duration_minutes) AS duration
            FROM gold.fact_trip t JOIN gold.dim_zone z ON z.location_id=t.dropoff_location_id
            WHERE t.data_month=%(start)s AND t.pickup_date BETWEEN %(date_from)s AND %(date_to)s
        """
    hourly = conn.execute(sql.SQL("""
        WITH demand AS (
            {demand}
    """).format(demand=sql.SQL(demand_source)) +
        sql.SQL(zone_filter) + sql.SQL("""
            GROUP BY 1
        )
        SELECT w.hour_local, extract(isodow FROM w.hour_local)::integer AS iso_weekday,
               w.temperature_c, w.precipitation_mm, (w.precipitation_mm>0) AS wet,
               w.observations, coalesce(d.trips,0)::bigint AS trips,
               coalesce(d.revenue,0) AS revenue, coalesce(d.fares,0) AS fares,
               coalesce(d.distance,0) AS distance, coalesce(d.duration,0) AS duration
        FROM gold.dim_weather w LEFT JOIN demand d ON d.hour_local=w.hour_local
        WHERE w.hour_local >= %(date_from)s AND w.hour_local < %(date_to)s + interval '1 day'
    """) + sql.SQL(weather_filter + ' ORDER BY w.hour_local'), args).fetchall()

    if role == 'pickup':
        zone_source = """
            SELECT a.location_id, sum(a.trip_count)::bigint AS trips,
                   sum(a.total_revenue) AS revenue, sum(a.total_fare) AS fares,
                   sum(a.total_distance) AS distance, sum(a.total_duration) AS duration
            FROM gold.agg_hourly_zone a JOIN gold.dim_weather w ON w.hour_local=a.pickup_hour
            WHERE a.data_month=%(start)s AND a.pickup_hour::date BETWEEN %(date_from)s AND %(date_to)s
        """
    else:
        zone_source = """
            SELECT t.dropoff_location_id AS location_id, count(*)::bigint AS trips,
                   sum(t.total_amount) AS revenue, sum(t.fare_amount) AS fares,
                   sum(t.trip_distance) AS distance, sum(t.duration_minutes) AS duration
            FROM gold.fact_trip t JOIN gold.dim_weather w ON w.hour_local=t.pickup_hour
            WHERE t.data_month=%(start)s AND t.pickup_date BETWEEN %(date_from)s AND %(date_to)s
        """
    zones = conn.execute(sql.SQL("""
        WITH metrics AS (
            {zone_source}
    """).format(zone_source=sql.SQL(zone_source)) +
        sql.SQL(weather_filter + """
            GROUP BY 1
        )
        SELECT z.location_id, z.zone_name, z.borough, m.trips, m.revenue,
               m.fares / nullif(m.trips, 0) AS average_fare,
               m.distance / nullif(m.trips, 0) AS average_distance,
               m.duration / nullif(m.trips, 0) AS average_duration,
               m.fares, m.distance, m.duration
        FROM metrics m JOIN gold.dim_zone z USING (location_id) WHERE TRUE
    """) + sql.SQL(zone_filter) + sql.SQL("""
        ORDER BY trips DESC, location_id
    """), args).fetchall()

    weather_groups = summarize_weather_groups(hourly)
    return dict(hourly=hourly, zones=zones, weather_groups=weather_groups)


def pipeline(conn, month, run_id, reason, page=1):
    runs = conn.execute("""
        SELECT run_id, status, source_kind, started_at, finished_at, rows_read, rows_loaded, rows_rejected
        FROM audit.pipeline_runs WHERE data_month=%s ORDER BY run_id DESC LIMIT 30
    """, (month,)).fetchall()
    if run_id < 0 or page < 1:
        raise ValueError('Invalid run or page')
    if not run_id:
        run_id = next((r['run_id'] for r in runs if r['status'] == 'success'), runs[0]['run_id'] if runs else 0)
    run = conn.execute("""
        SELECT run_id, status, source_kind, finished_at, rows_read, rows_loaded, rows_rejected, bronze_files, preview
        FROM audit.pipeline_runs WHERE data_month=%s AND run_id=%s
    """, (month, run_id)).fetchone()
    result = dict(runs=runs, run=run, reasons=[], rejected=[], page=1, total_pages=1, total_rows=0)
    if run and run['bronze_files'] is not None:
        result['reasons'] = conn.execute("""
            SELECT reason, records FROM quarantine.rejection_summary WHERE run_id=%s ORDER BY records DESC, reason
        """, (run_id,)).fetchall()
        total_rows = (
            next((int(r['records']) for r in result['reasons'] if r['reason'] == reason), 0)
            if reason else sum(int(r['records']) for r in result['reasons'])
        )
        total_pages = max(1, (total_rows + 19) // 20)
        current_page = min(page, total_pages)
        offset = (current_page - 1) * 20
        result['rejected'] = conn.execute("""
            SELECT source_row, reason, raw_record FROM quarantine.rejected_trip
            WHERE run_id=%s AND (%s::text IS NULL OR reason=%s)
            ORDER BY source_row LIMIT 20 OFFSET %s
        """, (run_id, reason, reason, offset)).fetchall()
        result['page'] = current_page
        result['total_pages'] = total_pages
        result['total_rows'] = total_rows
    return result


def dataset(conn, name, start, end, page=1):
    if name not in DATASETS or not 1 <= page < 10**8:
        raise ValueError('Invalid table or page')
    if name == 'dim_zone':
        count_args = ()
    elif name in ('dim_date', 'dim_weather'):
        count_args = (start, end)
    else:
        count_args = (start,)
    total_rows = int(conn.execute(DATASET_COUNTS[name], count_args).fetchone()['total'])
    total_pages = max(1, (total_rows + 24) // 25)
    current_page = min(page, total_pages)
    offset = (current_page - 1) * 25
    args = (*count_args, offset)
    rows = conn.execute(DATASETS[name], args).fetchall()
    return dict(table=name, rows=rows, page=current_page, total_pages=total_pages, total_rows=total_rows)


class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, body, kind):
        self.send_response(status)
        self.send_header('Content-Type', f'{kind}; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; object-src 'none'; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, data):
        self.send_body(status, json.dumps(data, default=str, allow_nan=False).encode(), 'application/json')

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path in ASSETS:
            filename, kind = ASSETS[url.path]
            self.send_body(200, (BASE_DIR / 'dashboard' / filename).read_bytes(), kind)
            return
        if url.path not in API_ROUTES:
            self.send_json(404, {'error': 'Endpoint not found'})
            return
        try:
            params = parse_qs(url.query, max_num_fields=12)

            def param(key, default):
                return params.get(key, [default])[0]

            with psycopg.connect(**connection_kwargs(), row_factory=dict_row) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                conn.execute("SET LOCAL statement_timeout = '25s'")
                if url.path == '/api/catalog':
                    data = catalog(conn)
                else:
                    start = date.fromisoformat(validate_month_arg(param('month', '')) + '-01')
                    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
                    if url.path == '/api/analytics':
                        data = analytics(conn, start, end, param)
                    elif url.path == '/api/distance':
                        data = analytics(conn, start, end, param, distance_only=True)
                    elif url.path == '/api/pipeline':
                        data = pipeline(conn, start, int(param('run', 0)), param('reason', None), int(param('page', 1)))
                    else:
                        data = dataset(conn, param('table', 'fact_trip'), start, end, int(param('page', 1)))
            self.send_json(200, data)
        except (ValueError, OverflowError, psycopg.errors.NumericValueOutOfRange):
            self.send_json(400, {'error': 'Check the month, filters and page parameters.'})
        except psycopg.Error:
            logging.exception('Dashboard query failed')
            self.send_json(503, {'error': 'Warehouse is unavailable or the query timed out. Try again.'})
        except (BrokenPipeError, ConnectionResetError):
            return


if __name__ == '__main__':
    print('NYC Taxi dashboard listening on port 8501', flush=True)
    ThreadingHTTPServer(('0.0.0.0', 8501), Handler).serve_forever()
