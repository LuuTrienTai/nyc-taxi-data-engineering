select 1 as failed
where (select count(*) from {{ ref('fact_trip') }})
   <> (select coalesce(sum(total_trips),0) from {{ ref('agg_daily_demand') }})
