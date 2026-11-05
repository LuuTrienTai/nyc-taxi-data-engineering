select f.pickup_location_id as zone_id,
       coalesce(z.borough, 'Unknown') as borough,
       coalesce(z.zone, 'Unknown') as zone,
       count(*) as pickup_count,
       sum(f.total_amount) as total_revenue
from {{ ref('fact_trip') }} f
left join {{ ref('dim_zone') }} z on f.pickup_location_id = z.zone_id
group by 1,2,3
