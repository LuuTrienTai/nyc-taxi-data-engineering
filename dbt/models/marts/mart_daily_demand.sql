select date_key as service_date,
       count(*) as trip_count,
       sum(total_amount) as total_revenue,
       avg(trip_distance) as avg_trip_distance,
       avg(total_amount) as avg_trip_revenue
from {{ ref('fact_trip') }}
group by 1
