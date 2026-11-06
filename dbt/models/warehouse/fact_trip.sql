-- Preserve every loaded trip; dimensions use LEFT JOIN to avoid losing unmatched zones/weather.
select
    t.data_month, t.trip_id,
    t.pickup_datetime, t.dropoff_datetime, t.pickup_datetime_utc,
    t.pickup_location_id, t.dropoff_location_id,
    zp.zone_name as pickup_zone_name, zp.borough as pickup_borough,
    zd.zone_name as dropoff_zone_name, zd.borough as dropoff_borough,
    t.trip_distance, t.passenger_count, t.fare_amount, t.tip_amount,
    t.total_amount, t.vendor_id, t.payment_type_id, t.rate_code_id,
    t.weather_hour_utc,
    w.temperature_c, w.precipitation_mm, w.rain_mm,
    w.snowfall_cm, w.wind_speed_kmh, w.weather_code
from {{ ref('stg_taxi_trips') }} t
left join {{ ref('dim_zone') }} zp on t.pickup_location_id = zp.location_id
left join {{ ref('dim_zone') }} zd on t.dropoff_location_id = zd.location_id
left join {{ ref('dim_weather_hourly') }} w on t.weather_hour_utc = w.observation_hour_utc
