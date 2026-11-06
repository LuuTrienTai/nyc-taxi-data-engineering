-- Join grain is a NEW YORK wall-clock hour. The repeated fall DST hour is
-- collapsed into one hour; weather comparisons during DST overlap are approximate.
select date_trunc('hour', observation_hour_local) as hour_local,
       avg(temperature_c) as temperature_c,
       sum(precipitation_mm) as precipitation_mm,
       count(*) as observations_in_hour
from {{ ref('stg_weather') }}
group by 1
