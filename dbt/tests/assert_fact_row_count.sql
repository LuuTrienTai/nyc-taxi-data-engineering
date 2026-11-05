-- Enrichment must not multiply or drop trips.
select 1 as mismatch
where (select count(*) from {{ ref('fact_trip') }})
   <> (select count(*) from {{ ref('stg_taxi_trips') }})
