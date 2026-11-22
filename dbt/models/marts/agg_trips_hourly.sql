-- Hourly aggregate for the "when" dashboard page (day of week x hour heatmap):
-- one row per pickup month x day of week x pickup hour x company (~8k rows for 2 years).
-- Stores sums and counts, not averages. `days` is how many calendar days went into the row
-- (4 or 5 Mondays in a month, for example), so the dashboard can show trips per day: trips / days.
--
-- Built like fct_trips, one month per run:
--   dbt build --select agg_trips_hourly --vars "{year: 2024, month: 1}"

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'insert_overwrite',
    partition_by = {
        'field': 'pickup_month',
        'data_type': 'date',
        'granularity': 'month',
        'copy_partitions': true
    }
) }}

with trips as (

    select
        pickup_date,
        pickup_at,
        license_number,
        base_passenger_fare,
        trip_duration_seconds
    from {{ ref('fct_trips') }}
    where pickup_date between date({{ var('year') }}, {{ var('month') }}, 1)
                          and last_day(date({{ var('year') }}, {{ var('month') }}, 1))

),

-- step 1: one row per day x hour x company
hourly as (

    select
        pickup_date,
        extract(hour from pickup_at) as pickup_hour,
        license_number,
        count(*)                     as trips,
        sum(base_passenger_fare)     as total_fare,
        sum(trip_duration_seconds)   as total_duration_seconds
    from trips
    group by pickup_date, pickup_hour, license_number

),

-- step 2: collapse the days of the month into their day of week
weekly as (

    select
        date_trunc(hourly.pickup_date, month) as pickup_month,
        dates.year_month,
        dates.day_of_week,
        dates.day_name,
        hourly.pickup_hour,
        companies.company,
        count(*)                              as days,
        sum(hourly.trips)                     as trips,
        sum(hourly.total_fare)                as total_fare,
        sum(hourly.total_duration_seconds)    as total_duration_seconds
    from hourly
    left join {{ ref('dim_date') }}    as dates     on hourly.pickup_date = dates.date_day
    left join {{ ref('dim_company') }} as companies on hourly.license_number = companies.license_number
    group by pickup_month, year_month, day_of_week, day_name, pickup_hour, company

)

select * from weekly
