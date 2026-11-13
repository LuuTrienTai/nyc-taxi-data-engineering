with f as (select data_month,count(*) n,sum(total_amount) revenue from {{ source('gold','fact_trip') }} group by 1),
a as (select data_month,sum(trip_count) n,sum(total_revenue) revenue from {{ source('gold','agg_daily_demand') }} group by 1)
select coalesce(f.data_month,a.data_month) as data_month from f full join a using(data_month)
where f.n is distinct from a.n or f.revenue is distinct from a.revenue
