select observation_hour_utc,
       observation_hour_utc at time zone 'America/New_York' as observation_hour_local,
       temperature_c, precipitation_mm
from {{ source('raw','weather_hourly') }}
