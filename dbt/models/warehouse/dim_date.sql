with pickup_dates as (
    select distinct pickup_datetime::date as date_key
    from {{ ref('stg_taxi_trips') }}
    where pickup_datetime is not null
)
select date_key,
    extract(year from date_key)::int as year,
    extract(quarter from date_key)::int as quarter,
    extract(month from date_key)::int as month,
    extract(day from date_key)::int as day,
    extract(isodow from date_key)::int as iso_weekday
from pickup_dates
