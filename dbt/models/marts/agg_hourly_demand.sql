select date_trunc('hour', pickup_datetime) as pickup_hour,
    count(*) as total_trips, sum(total_amount) as total_revenue,
    avg(fare_amount) as avg_fare
from {{ ref('fact_trip') }}
where pickup_datetime is not null
group by 1
