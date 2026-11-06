select data_month, pickup_location_id, max(pickup_zone_name) as pickup_zone_name,
    max(pickup_borough) as pickup_borough,
    count(*) as total_trips, sum(total_amount) as total_revenue,
    avg(trip_distance) as avg_distance
from {{ ref('fact_trip') }}
group by 1, 2
