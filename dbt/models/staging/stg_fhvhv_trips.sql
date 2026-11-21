-- Staging for High Volume FHV trips: one row per trip, same grain as the source.
-- Only renames, type fixes and light standardization. No rows are removed here.
-- Materialized as a view (dbt_project.yml): no data is copied; queries read the GCS files.

with source as (

    select * from {{ source('raw', 'fhvhv_trips') }}

),

renamed as (

    select
        -- partitions: filter on these to read fewer files (and pay less)
        year  as partition_year,
        month as partition_month,

        -- company and bases
        hvfhs_license_num as license_number,
        case hvfhs_license_num
            when 'HV0002' then 'Juno'
            when 'HV0003' then 'Uber'
            when 'HV0004' then 'Via'
            when 'HV0005' then 'Lyft'
            else 'Unknown'
        end as company,
        dispatching_base_num as dispatching_base_number,
        originating_base_num as originating_base_number,  -- ~99.7% null for Lyft: not reported

        -- timestamps
        request_datetime  as requested_at,
        on_scene_datetime as on_scene_at,                 -- ~99.7% null for Lyft: not reported
        pickup_datetime   as pickup_at,
        dropoff_datetime  as dropoff_at,

        -- locations (taxi zone ids, see taxi_zone_lookup.csv)
        PULocationID as pickup_location_id,
        DOLocationID as dropoff_location_id,

        -- trip
        trip_miles,
        trip_time as trip_duration_seconds,

        -- money, in USD
        base_passenger_fare,
        tolls,
        bcf as black_car_fund_fee,
        sales_tax,
        congestion_surcharge,
        airport_fee,
        -- Manhattan congestion pricing started in January 2025: the column does not exist
        -- in 2024 files, so it reads as NULL there. No fee was charged, so 0 is the true value.
        coalesce(cbd_congestion_fee, 0) as cbd_congestion_fee,
        tips,
        driver_pay,

        -- Y/N flags as booleans
        shared_request_flag = 'Y' as is_shared_ride_requested,
        shared_match_flag   = 'Y' as is_shared_ride_matched,
        access_a_ride_flag  = 'Y' as is_access_a_ride,
        wav_request_flag    = 'Y' as is_wheelchair_requested,
        wav_match_flag      = 'Y' as is_wheelchair_matched

    from source

)

select * from renamed
