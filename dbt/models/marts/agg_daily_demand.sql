select data_month, date_trunc('day', pickup_datetime) as pickup_day,
    count(*) as total_trips, sum(total_amount) as total_revenue
from {{ ref('fact_trip') }}
where pickup_datetime is not null
group by 1, 2
