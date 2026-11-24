"""Independently reconcile committed Gold and Quarantine with the run audit."""
import argparse
from datetime import date

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
    with psycopg.connect(**connection_kwargs()) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        run = conn.execute("""
            SELECT run_id, rows_read, rows_loaded, rows_rejected FROM audit.pipeline_runs
            WHERE data_month = %s AND status = 'success' ORDER BY run_id DESC LIMIT 1
        """, (start,)).fetchone()
        if run is None:
            raise ValueError(f'No successful load for {month}')
        count, revenue = reconcile(conn, start, *run)
    print(f'[PASS] {month} · run {run[0]} · {count:,} trips · ${revenue:,.2f} · all three marts reconcile')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', required=True)
    verify_month(parser.parse_args().month)
