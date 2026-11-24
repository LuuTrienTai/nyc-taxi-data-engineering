WITH facts AS (
    SELECT data_month, count(*) AS trips, sum(total_amount) AS revenue
    FROM {{ source('gold','fact_trip') }}
    GROUP BY data_month
)
{% for mart in ('agg_hourly_zone', 'agg_daily_trips', 'agg_zone_revenue') %}
SELECT '{{ mart }}' AS mart, coalesce(facts.data_month, m.data_month) AS data_month
FROM facts FULL JOIN (
    SELECT data_month, sum(trip_count) AS trips, sum(total_revenue) AS revenue
    FROM {{ source('gold',mart) }}
    GROUP BY data_month
) m USING (data_month)
WHERE facts.trips IS DISTINCT FROM m.trips OR facts.revenue IS DISTINCT FROM m.revenue
{% if not loop.last %}UNION ALL{% endif %}
{% endfor %}
