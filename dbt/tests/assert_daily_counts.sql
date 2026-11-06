select 1 as failed
where (select count(*) from {{ ref('fact_trip') }})
   <> (select coalesce(sum(trip_count),0) from {{ ref('mart_daily_demand') }})
