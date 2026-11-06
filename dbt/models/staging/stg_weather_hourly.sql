select observation_hour_utc, observation_hour_ny,
    temperature_c, precipitation_mm, rain_mm, snowfall_cm,
    wind_speed_kmh, weather_code
from {{ source('raw_staging','weather_hourly') }}
