select distinct
  pickup_date as date_key,
  extract(year from pickup_date)::int as year,
  extract(quarter from pickup_date)::int as quarter,
  extract(month from pickup_date)::int as month,
  extract(day from pickup_date)::int as day,
  extract(isodow from pickup_date)::int as iso_weekday
from {{ ref('stg_trips') }}
