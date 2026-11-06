"""Profile one loaded staging month."""
import argparse

import psycopg

from src.warehouse.load_staging import connection_kwargs, parse_month


def run_eda(month_str: str) -> None:
    month = parse_month(month_str)
    with psycopg.connect(**connection_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT count(*) AS trips,
                   min(pickup_datetime) AS first_pickup,
                   max(pickup_datetime) AS last_pickup,
                   count(*) - count(pickup_location_id) AS missing_pickup_zone,
                   count(*) - count(weather_hour_utc) AS missing_weather_hour,
                   count(*) - count(fare_amount) AS missing_fare,
                   round(avg(fare_amount)::numeric, 2) AS avg_fare,
                   round(avg(trip_distance)::numeric, 2) AS avg_distance
            FROM staging.taxi_trips
            WHERE data_month = %s
        """, (month,))
        summary = cur.fetchone()
        if summary[0] == 0:
            raise SystemExit(f"No staging taxi rows for {month_str}")
        print(f"Staging EDA for {month_str}")
        for column, value in zip(cur.description, summary):
            print(f"{column.name}: {value}")

        cur.execute("""
            SELECT pickup_location_id, count(*) AS trips
            FROM staging.taxi_trips WHERE data_month = %s
            GROUP BY 1 ORDER BY trips DESC, pickup_location_id LIMIT 5
        """, (month,))
        print("Top 5 pickup zones (location_id, trips):", cur.fetchall())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    run_eda(parser.parse_args().month)
