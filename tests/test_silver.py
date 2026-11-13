import unittest
import pandas as pd
from src.processing.silver import clean_batch

class SilverTests(unittest.TestCase):
    def raw(self):
        return pd.DataFrame([dict(tpep_pickup_datetime='2025-01-02 10:00',tpep_dropoff_datetime='2025-01-02 10:15',PULocationID=1,DOLocationID=2,trip_distance=2.,fare_amount=10.,total_amount=12.)])
    def test_valid_missing_optional(self):
        good,bad=clean_batch(self.raw(),'2025-01',0,{1,2});self.assertEqual((len(good),len(bad)),(1,0));self.assertTrue(good.passenger_count.isna().all())
    def test_identical_trips_preserved(self):
        raw=pd.concat([self.raw(),self.raw()],ignore_index=True)
        good,bad=clean_batch(raw,'2025-01',20,{1,2});self.assertEqual(good.source_row.tolist(),[21,22])
    def test_invalid_distance(self):
        raw=self.raw();raw.loc[0,'trip_distance']=-1
        good,bad=clean_batch(raw,'2025-01',0,{1,2});self.assertEqual(bad.reason.iloc[0],'invalid_trip_distance')
    def test_missing_column(self):
        with self.assertRaises(ValueError):clean_batch(self.raw().drop(columns=['fare_amount']),'2025-01',0,{1,2})
    def test_month_boundary(self):
        raw=self.raw();raw['tpep_pickup_datetime']='2025-02-01 00:00';raw['tpep_dropoff_datetime']='2025-02-01 00:15'
        good,bad=clean_batch(raw,'2025-01',0,{1,2});self.assertEqual(bad.reason.iloc[0],'out_of_month')
    def test_nonfinite_amount(self):
        raw=self.raw();raw['total_amount']=float('inf')
        good,bad=clean_batch(raw,'2025-01',0,{1,2});self.assertEqual(len(bad),1)
    def test_unknown_zone(self):
        good,bad=clean_batch(self.raw(),'2025-01',0,{1});self.assertEqual(bad.reason.iloc[0],'unknown_zone')
    def test_dst_overlap_flag(self):
        raw=self.raw();raw['tpep_pickup_datetime']='2025-11-02 01:15';raw['tpep_dropoff_datetime']='2025-11-02 01:30'
        good,bad=clean_batch(raw,'2025-11',0,{1,2});self.assertTrue(good.dst_ambiguous.iloc[0])
    def test_nonexistent_dst_hour(self):
        raw=self.raw();raw['tpep_pickup_datetime']='2025-03-09 02:15';raw['tpep_dropoff_datetime']='2025-03-09 02:30'
        good,bad=clean_batch(raw,'2025-03',0,{1,2});self.assertEqual(bad.reason.iloc[0],'nonexistent_dst_hour')
if __name__=='__main__':unittest.main()

