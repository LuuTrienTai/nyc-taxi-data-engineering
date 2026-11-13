import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from src.pipeline import prepare_dimensions
class DimensionTests(unittest.TestCase):
    def setup_data(self,month,missing=False):
        start=pd.Timestamp(month+'-01');end=start+pd.offsets.MonthBegin(1)
        utc=pd.date_range(start.tz_localize('UTC'),(end+pd.Timedelta(days=1)).tz_localize('UTC'),freq='h',inclusive='left')
        weather=pd.DataFrame({'observation_time_utc':utc.strftime('%Y-%m-%dT%H:%M'),'temperature_2m':5.,'precipitation':0.})
        if missing:weather=weather.drop(index=10)
        return weather
    def check_month(self,month,expected,missing=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'taxi_zone_lookup.csv').write_text('LocationID,Borough,Zone,service_zone\n265,Unknown,NA,N/A\n')
            self.setup_data(month,missing).to_parquet(root/f'weather_{month}.parquet')
            with patch('src.pipeline.BRONZE_ZONES_DIR',root),patch('src.pipeline.BRONZE_WEATHER_DIR',root):
                z,w=prepare_dimensions(month)
                self.assertEqual(z.zone_name.iloc[0],'NA');self.assertEqual(len(w),expected)
                return w
    def test_january(self):self.check_month('2025-01',744)
    def test_spring_dst(self):self.check_month('2025-03',743)
    def test_fall_dst(self):
        w=self.check_month('2025-11',720);self.assertEqual(w.observations.max(),2)
    def test_missing_weather_rejected(self):
        with self.assertRaises(ValueError):self.check_month('2025-01',744,True)
