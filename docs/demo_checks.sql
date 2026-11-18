-- Demo Check: Verify no duplicate trip IDs
SELECT COUNT(*) - COUNT(DISTINCT trip_id) as duplicate_trips FROM warehouse.fact_trip;

-- Demo Check: Verify data range
SELECT MIN(pickup_datetime) as earliest_trip, MAX(pickup_datetime) as latest_trip FROM warehouse.fact_trip;