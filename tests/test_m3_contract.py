"""Lightweight schema and CLI contract checks (no database required)."""
import unittest
from datetime import date
from pathlib import Path


class M3ContractTests(unittest.TestCase):
    def test_sql_has_expected_staging_tables(self):
        sql = (Path(__file__).resolve().parents[1] / 'docker/postgres/init/02_staging.sql').read_text()
        for table in ('taxi_trips', 'weather_hourly', 'zones'):
            self.assertIn(f'CREATE TABLE IF NOT EXISTS staging.{table}', sql)

    def test_month_validation(self):
        from src.warehouse.load_staging import parse_month
        self.assertEqual(parse_month('2025-01'), date(2025, 1, 1))
        for bad in ('2025-13', 'abc', '2025-1'):
            with self.assertRaises(ValueError):
                parse_month(bad)


if __name__ == '__main__':
    unittest.main()
