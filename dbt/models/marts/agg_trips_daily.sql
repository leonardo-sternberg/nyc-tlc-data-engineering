-- Daily aggregate for dashboards: one row per pickup day x company x pickup zone (~380k rows for 2 years).
-- Dashboards read this small table instead of fct_trips (~483M rows), so each chart costs a few MB.
-- Stores sums and counts, not averages: the dashboard computes averages (e.g. total_fare / trips)
-- correctly for any filter. Dimension names are copied in, so the dashboard needs no joins.
--
-- Built like fct_trips, one month per run (reading all months at once would bill ~35 GB):
--   dbt build --select agg_trips_daily --vars "{year: 2024, month: 1}"

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'insert_overwrite',
    partition_by = {
        'field': 'pickup_date',
        'data_type': 'date',
        'granularity': 'month',
        'copy_partitions': true
    }
) }}

with trips as (

    select
        pickup_date,
        license_number,
        pickup_location_id,
        base_passenger_fare,
        tips,
        driver_pay,
        trip_miles,
        trip_duration_seconds,
        cbd_congestion_fee,
        is_negative_fare
    from {{ ref('fct_trips') }}
    where pickup_date between date({{ var('year') }}, {{ var('month') }}, 1)
                          and last_day(date({{ var('year') }}, {{ var('month') }}, 1))

),

daily as (

    select
        pickup_date,
        license_number,
        pickup_location_id,
        count(*)                   as trips,
        sum(base_passenger_fare)   as total_fare,
        sum(tips)                  as total_tips,
        sum(driver_pay)            as total_driver_pay,
        sum(trip_miles)            as total_miles,
        sum(trip_duration_seconds) as total_duration_seconds,
        sum(cbd_congestion_fee)    as total_cbd_congestion_fee,
        countif(is_negative_fare)  as negative_fare_trips
    from trips
    group by pickup_date, license_number, pickup_location_id

)

select
    -- when
    daily.pickup_date,
    dates.year_month,
    dates.day_name,
    dates.is_weekend,

    -- who and where
    companies.company,
    daily.pickup_location_id,
    zones.borough   as pickup_borough,
    zones.zone_name as pickup_zone_name,

    -- measures
    daily.trips,
    daily.total_fare,
    daily.total_tips,
    daily.total_driver_pay,
    daily.total_miles,
    daily.total_duration_seconds,
    daily.total_cbd_congestion_fee,
    daily.negative_fare_trips

from daily
left join {{ ref('dim_date') }}    as dates     on daily.pickup_date = dates.date_day
left join {{ ref('dim_company') }} as companies on daily.license_number = companies.license_number
left join {{ ref('dim_zone') }}    as zones     on daily.pickup_location_id = zones.zone_id
