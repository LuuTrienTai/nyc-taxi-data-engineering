select location_id, borough, zone_name, service_zone
from {{ source('raw_staging','zones') }}
