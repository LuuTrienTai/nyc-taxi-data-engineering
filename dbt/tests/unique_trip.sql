select data_month,source_row from {{ source('gold','fact_trip') }} group by 1,2 having count(*)>1
