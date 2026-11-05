from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestWeek2Structure(unittest.TestCase):
    def test_expected_models_present(self):
        for f in ('staging/stg_taxi_trips.sql', 'warehouse/fact_trip.sql',
                  'warehouse/dim_zone.sql', 'warehouse/dim_weather_hourly.sql',
                  'marts/agg_hourly_demand.sql', 'marts/agg_daily_demand.sql',
                  'marts/agg_zone_demand.sql'):
            with self.subTest(f=f):
                self.assertTrue((ROOT / 'dbt/models' / f).is_file())

    def test_fact_references_sources_via_dbt(self):
        fact = (ROOT / 'dbt/models/warehouse/fact_trip.sql').read_text()
        self.assertIn("ref('stg_taxi_trips')", fact)
        self.assertIn('left join', fact.lower())

    def test_no_old_monthly_table_dependency(self):
        for file in (ROOT / 'dbt/models').rglob('*.sql'):
            self.assertNotIn('taxi_2026_01', file.read_text())

if __name__ == '__main__':
    unittest.main()
