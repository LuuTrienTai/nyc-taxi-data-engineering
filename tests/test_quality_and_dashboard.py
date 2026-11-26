import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.dashboard import analytics, summarize_weather_groups
from src.pipeline import trip_digest
from src.processing.silver import REQUIRED
from src.quality import check_taxi_schema


class QualityAndDashboardTests(unittest.TestCase):
    def test_check_taxi_schema_valid_and_missing(self):
        check_taxi_schema(REQUIRED + ['extra'])
        with self.assertRaisesRegex(ValueError, 'missing columns'):
            check_taxi_schema([c for c in REQUIRED if c != 'fare_amount'])

    def test_trip_digest_deterministic(self):
        from datetime import datetime
        clean = SimpleNamespace(
            pickup_datetime=datetime(2025, 1, 2, 10, 0, 0),
            dropoff_datetime=datetime(2025, 1, 2, 10, 15, 0),
            pickup_location_id=1,
            dropoff_location_id=2,
            trip_distance=2.5,
            fare_amount=12.0,
            total_amount=15.5,
        )
        d1 = trip_digest(clean, (1, 1, 1, 1, 2.0, None, None, None, None, None, None, None))
        d2 = trip_digest(clean, (1, 1, 1, 1, 2.0, None, None, None, None, None, None, None))
        d3 = trip_digest(clean, (2, 1, 1, 1, 2.0, None, None, None, None, None, None, None))
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, d3)
        self.assertEqual(len(d1.hex()), 32)

    def test_weather_groups_sorted_numerically(self):
        hourly = [
            {'temperature_c': 12.0, 'trips': 10, 'precipitation_mm': 0.0},
            {'temperature_c': -3.0, 'trips': 4, 'precipitation_mm': 0.5},
            {'temperature_c': 6.0, 'trips': 8, 'precipitation_mm': 0.0},
            {'temperature_c': 14.0, 'trips': 20, 'precipitation_mm': 1.0},
        ]
        groups = summarize_weather_groups(hourly)
        self.assertEqual(
            [g['temperature_band'] for g in groups],
            ['-5 to under 0 °C', '5 to under 10 °C', '10 to under 15 °C'],
        )
        self.assertEqual(groups[2]['hours'], 2)
        self.assertEqual(groups[2]['trips'], 30)
        self.assertEqual(groups[2]['trips_per_hour'], 15.0)

    def test_analytics_rejects_invalid_filters(self):
        from datetime import date
        conn = MagicMock()
        start, end = date(2025, 1, 1), date(2025, 2, 1)

        with self.assertRaisesRegex(ValueError, 'location role'):
            analytics(conn, start, end, lambda k, d: 'invalid' if k == 'location_role' else d)
        with self.assertRaisesRegex(ValueError, 'outside the selected month'):
            analytics(conn, start, end, lambda k, d: '2025-02-01' if k == 'date_to' else d)
        with self.assertRaisesRegex(ValueError, 'weather filter'):
            analytics(conn, start, end, lambda k, d: 'storm' if k == 'weather' else d)
        with self.assertRaisesRegex(ValueError, 'hour filter'):
            analytics(conn, start, end, lambda k, d: '25' if k == 'hour' else d)


if __name__ == '__main__':
    unittest.main()
