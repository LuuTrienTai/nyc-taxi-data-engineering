"""Compare a month-level fact aggregation to reading the daily mart."""
import argparse

import psycopg

from src.config import connection_kwargs
from src.ingestion.taxi import validate_month_arg


def benchmark(month):
    start = validate_month_arg(month) + '-01'
    queries = {
        'FACT': """SELECT pickup_date, count(*) AS trip_count, sum(total_amount) AS total_revenue
                   FROM gold.fact_trip WHERE data_month=%s GROUP BY pickup_date ORDER BY pickup_date""",
        'GOLD MART': """SELECT pickup_date, trip_count, total_revenue FROM gold.agg_daily_trips
                        WHERE data_month=%s ORDER BY pickup_date""",
    }
    with psycopg.connect(**connection_kwargs()) as conn:
        for label, query in queries.items():
            print(label, flush=True)
            for row in conn.execute('EXPLAIN (ANALYZE, BUFFERS) ' + query, (start,)):
                print(row[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', required=True)
    benchmark(parser.parse_args().month)
