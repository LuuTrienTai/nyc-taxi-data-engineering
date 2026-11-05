select f.pickup_hour_local,
       count(*) as trip_count,
       sum(f.total_amount) as total_revenue,
       w.temperature_c,
       w.precipitation_mm,
       w.observations_in_hour
from {{ ref('fact_trip') }} f
left join {{ ref('dim_weather_hour') }} w
  on f.pickup_hour_local = w.hour_local
group by 1,4,5,6
