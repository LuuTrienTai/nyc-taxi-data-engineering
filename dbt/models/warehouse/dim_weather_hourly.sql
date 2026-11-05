-- Weather UTC values are normalized naive timestamps (UTC wall-clock).
-- One row per UTC hour across all months, to avoid duplicate joins on month boundaries.
select observation_hour_utc,
    max(observation_hour_ny) as observation_hour_ny,
    max(temperature_c) as temperature_c,
    max(precipitation_mm) as precipitation_mm,
    max(rain_mm) as rain_mm,
    max(snowfall_cm) as snowfall_cm,
    max(wind_speed_kmh) as wind_speed_kmh,
    max(weather_code) as weather_code
from {{ ref('stg_weather_hourly') }}
group by observation_hour_utc
