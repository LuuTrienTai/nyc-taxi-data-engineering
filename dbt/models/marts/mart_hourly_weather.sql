-- UTC keeps the two repeated fall DST hours separate.
select data_month, weather_hour_utc,
    max(date_trunc('hour', pickup_datetime)) as pickup_hour_local,
    count(*) as total_trips, sum(total_amount) as total_revenue,
    max(temperature_c) as temperature_c,
    max(precipitation_mm) as precipitation_mm
from {{ ref('fact_trip') }}
where weather_hour_utc is not null
group by 1, 2
