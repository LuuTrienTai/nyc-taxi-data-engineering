select z.borough,z.zone_name,a.* from {{ source('gold','agg_zone_demand') }} a join {{ source('gold','dim_zone') }} z using(location_id)
