"""Check one staged month against the fact and each published demand mart."""
import argparse

import psycopg
from psycopg import sql

from src.warehouse.load_staging import connection_kwargs, parse_month

MARTS = (
    ("agg_daily_demand", "pickup_day", "date_trunc('day', pickup_datetime)"),
    ("agg_hourly_demand", "pickup_hour", "date_trunc('hour', pickup_datetime)"),
    ("agg_zone_demand", "pickup_location_id", "pickup_location_id"),
)


def validate_aggregations(month_str: str) -> None:
    month = parse_month(month_str)
    with psycopg.connect(**connection_kwargs()) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        with conn.cursor() as cur:
            totals = []
            for schema, table in (("staging", "taxi_trips"), ("warehouse", "fact_trip")):
                cur.execute(sql.SQL("""
                    SELECT count(*), round(coalesce(sum(total_amount), 0)::numeric, 2)
                    FROM {} WHERE data_month = %s
                """).format(sql.Identifier(schema, table)), (month,))
                totals.append(cur.fetchone())
            if totals[0][0] == 0 or totals[0] != totals[1]:
                raise RuntimeError(f"{month_str}: staging (trips, revenue)={totals[0]}, fact={totals[1]}")

            for mart, key, expression in MARTS:
                cur.execute(sql.SQL("""
                    WITH expected AS (
                        SELECT {expression} AS bucket, count(*) AS trips,
                               round(sum(total_amount)::numeric, 2) AS revenue
                        FROM staging.taxi_trips
                        WHERE data_month = %s
                        GROUP BY 1
                    ), actual AS (
                        SELECT {key} AS bucket, total_trips AS trips,
                               round(total_revenue::numeric, 2) AS revenue
                        FROM {mart}
                        WHERE data_month = %s
                    )
                    SELECT count(*) FROM (
                        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual)
                        UNION ALL
                        (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)
                    ) AS differences
                """).format(
                    expression=sql.SQL(expression),
                    key=sql.Identifier(key),
                    mart=sql.Identifier("marts", mart),
                ), (month, month))
                mismatches = cur.fetchone()[0]
                if mismatches:
                    raise RuntimeError(f"{month_str}: marts.{mart} has {mismatches} differing rows")
                print(f"[PASS] marts.{mart}: trip count and revenue match staging for every group")

    trips, revenue = totals[0]
    print(f"[PASS] {month_str}: staging = fact = Gold | trips={trips} | revenue={revenue}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    validate_aggregations(parser.parse_args().month)
