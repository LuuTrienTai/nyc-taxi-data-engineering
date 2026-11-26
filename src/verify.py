"""Independently reconcile committed Gold and Quarantine with the run audit."""
import argparse
import json
from datetime import date, timedelta

import psycopg
from psycopg import sql

from src.config import connection_kwargs
from src.ingestion.taxi import validate_month_arg

MARTS = ('agg_hourly_zone', 'agg_daily_trips', 'agg_zone_revenue')


def reconcile(conn, month, run_id, read, loaded, rejected):
    facts = conn.execute("""
        SELECT count(*), sum(total_amount) FROM gold.fact_trip WHERE data_month = %s
    """, (month,)).fetchone()
    bad = conn.execute("""
        SELECT count(*) FROM quarantine.rejected_trip WHERE run_id = %s
    """, (run_id,)).fetchone()[0]
    if not loaded or facts[0] != loaded or bad != rejected or read != loaded + rejected:
        raise ValueError(f'Run {run_id}: Bronze, Gold and Quarantine row counts do not reconcile')
    for table in MARTS:
        totals = conn.execute(sql.SQL("""
            SELECT sum(trip_count), sum(total_revenue) FROM {} WHERE data_month = %s
        """).format(sql.Identifier('gold', table)), (month,)).fetchone()
        if totals != facts:
            raise ValueError(f'Run {run_id}: {table} count or revenue differs from fact_trip')
    return facts


def verify_month(month):
    start = date.fromisoformat(validate_month_arg(month) + '-01')
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    with psycopg.connect(**connection_kwargs()) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')

        forbidden = conn.execute("""
            SELECT table_schema || '.' || table_name
            FROM information_schema.tables
            WHERE table_schema IN ('staging', 'silver')
               OR (table_schema = 'public' AND table_name LIKE '%taxi%')
        """).fetchall()
        if forbidden:
            raise ValueError(f"Unexpected staging/Silver tables found: {[r[0] for r in forbidden]}")

        run = conn.execute("""
            SELECT run_id, rows_read, rows_loaded, rows_rejected, source_kind, bronze_files
            FROM audit.pipeline_runs
            WHERE data_month = %s AND status = 'success'
            ORDER BY run_id DESC LIMIT 1
        """, (start,)).fetchone()
        if run is None:
            raise ValueError(f'No successful load for {month}')

        run_id, rows_read, rows_loaded, rows_rejected, source_kind, bronze_files = run
        rows_read = int(rows_read)
        rows_loaded = int(rows_loaded)
        rows_rejected = int(rows_rejected)
        count, revenue = reconcile(conn, start, run_id, rows_read, rows_loaded, rows_rejected)
        count = int(count)

        reason_rows = conn.execute("""
            SELECT reason, records FROM quarantine.rejection_summary
            WHERE run_id = %s ORDER BY records DESC, reason
        """, (run_id,)).fetchall()
        rejection_reasons = {r: int(c) for r, c in reason_rows}

        avg_fare, avg_distance, avg_duration = conn.execute("""
            SELECT coalesce(avg(fare_amount), 0),
                   coalesce(avg(trip_distance), 0),
                   coalesce(avg(duration_minutes), 0)
            FROM gold.fact_trip WHERE data_month = %s
        """, (start,)).fetchone()

        dim_date_rows = int(conn.execute(
            'SELECT count(*) FROM gold.dim_date WHERE date_key >= %s AND date_key < %s',
            (start, end),
        ).fetchone()[0])
        dim_zone_rows = int(conn.execute('SELECT count(*) FROM gold.dim_zone').fetchone()[0])
        dim_weather_rows = int(conn.execute(
            'SELECT count(*) FROM gold.dim_weather WHERE hour_local >= %s AND hour_local < %s',
            (start, end),
        ).fetchone()[0])

        marts_summary = {}
        for table in MARTS:
            m_rows, m_trips, m_rev = conn.execute(sql.SQL("""
                SELECT count(*), coalesce(sum(trip_count), 0), coalesce(sum(total_revenue), 0)
                FROM {} WHERE data_month = %s
            """).format(sql.Identifier('gold', table)), (start,)).fetchone()
            marts_summary[table] = {
                'rows': int(m_rows),
                'trip_count': int(m_trips),
                'total_revenue': f'{float(m_rev):.2f}',
            }

    pass_pct = (rows_loaded / rows_read * 100.0) if rows_read else 0.0
    reject_pct = (rows_rejected / rows_read * 100.0) if rows_read else 0.0
    files_info = [
        {
            'file': item.get('file'),
            'rows': item.get('rows'),
            'sha256': (item.get('sha256') or '')[:12],
        }
        for item in (bronze_files or [])
    ]

    summary = {
        'month': month,
        'run_id': int(run_id),
        'source_kind': source_kind,
        'bronze': {
            'rows_read': rows_read,
            'files': files_info,
        },
        'silver_quarantine': {
            'silver_valid': rows_loaded,
            'quarantine_rejected': rows_rejected,
            'persisted_silver_tables': 0,
            'rejection_reasons': rejection_reasons,
        },
        'gold': {
            'fact_rows': count,
            'revenue': f'{float(revenue):.2f}',
            'avg_fare': f'{float(avg_fare):.2f}',
            'avg_distance': f'{float(avg_distance):.2f}',
            'avg_duration': f'{float(avg_duration):.2f}',
            'dims': {
                'dim_date': dim_date_rows,
                'dim_zone': dim_zone_rows,
                'dim_weather': dim_weather_rows,
            },
            'marts': marts_summary,
        },
        'checks': 'PASS',
    }

    print(f"\n=== 3-Layer Verification Summary ({month}, run_id={run_id}, source={source_kind}) ===")
    file_desc = ', '.join(
        f"{f['file']}({f['sha256']}...)" for f in files_info
    ) or 'none'
    print(f"[1. BRONZE]             rows_read={rows_read:,} | files={file_desc}")
    print(
        f"[2. SILVER/QUARANTINE]  silver_valid={rows_loaded:,} ({pass_pct:.2f}%) | "
        f"quarantine_rejected={rows_rejected:,} ({reject_pct:.2f}%) | persisted_silver_tables=0"
    )
    if rejection_reasons:
        reasons_txt = ', '.join(f"{r}={c:,}" for r, c in rejection_reasons.items())
        print(f"    Quarantine reasons: {reasons_txt}")
    else:
        print("    Quarantine reasons: none (0 rejected)")
    print(
        f"[3. GOLD]               fact_trip={count:,} | total_revenue=${float(revenue):,.2f} | "
        f"avg_fare=${float(avg_fare):.2f} | avg_dist={float(avg_distance):.2f} mi | "
        f"avg_dur={float(avg_duration):.2f} min"
    )
    print(
        f"    Dimensions:         dim_date={dim_date_rows:,} | dim_zone={dim_zone_rows:,} | "
        f"dim_weather={dim_weather_rows:,}"
    )
    for table, info in marts_summary.items():
        print(
            f"    {table:<20s} rows={info['rows']:,} | trips={info['trip_count']:,} | "
            f"revenue=${float(info['total_revenue']):,.2f} [RECONCILED]"
        )
    print(f"[PASS] {month} · run {run_id} · {count:,} trips · ${revenue:,.2f} · all three layers reconciled")
    print(json.dumps(summary, default=str))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', required=True)
    verify_month(parser.parse_args().month)
