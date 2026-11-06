-- dbt singular test: result must be empty
select data_month, trip_id, count(*) as n
from {{ ref('fact_trip') }}
group by 1,2
having count(*) > 1
