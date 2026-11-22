-- Zone dimension: one row per TLC taxi zone (265 rows).
-- Used twice by fct_trips (role-playing dimension): as pickup zone and as dropoff zone.
-- The TLC zone id is stable and already an integer, so it is the key (no surrogate key needed).

with zones as (

    select * from {{ ref('taxi_zone_lookup') }}

)

select
    LocationID   as zone_id,
    Borough      as borough,
    Zone         as zone_name,
    service_zone,
    -- 264 and 265 are TLC placeholders for unknown / outside NYC locations
    LocationID in (264, 265) as is_unknown_zone

from zones
