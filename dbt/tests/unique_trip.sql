SELECT data_month, trip_id FROM {{ source('gold','fact_trip') }}
GROUP BY data_month, trip_id
HAVING count(*) > 1
