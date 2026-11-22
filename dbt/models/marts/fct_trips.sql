-- Trip fact: one row per High Volume FHV trip (Uber, Lyft). Grain = one trip.
-- Keys: pickup_date -> dim_date, pickup/dropoff_location_id -> dim_zone (twice),
-- license_number -> dim_company. Descriptive attributes live in the dimensions.
--
-- Incremental, one month per run (insert_overwrite replaces that month's daily partitions,
-- so re-running a month does not duplicate rows):
--   dbt run --select fct_trips --vars "{year: 2024, month: 1}"
-- The month filter always applies, also on the first run: reading all 24 months at once
-- would exceed the 30 GB bytes-billed cap. It also makes BigQuery open only that month's file.
-- Careful: --full-refresh drops the table and rebuilds it with ONLY the month passed in --vars.
-- Use it only when the columns change, then reload every month.
--
-- Negative fares (refunds/adjustments) are kept and flagged with is_negative_fare.
--
-- copy_partitions: the new days are moved in with a BigQuery copy job (free) instead of a
-- MERGE query, which would read the month a second time (~2.9 GB more per month).

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'insert_overwrite',
    partition_by = {'field': 'pickup_date', 'data_type': 'date', 'copy_partitions': true},
    cluster_by = ['license_number', 'pickup_location_id']
) }}

with trips as (
    select * from {{ ref('stg_fhvhv_trips') }}
    where partition_year = {{ var('year') }}
      and partition_month = {{ var('month') }}
)

select
    date(pickup_at) as pickup_date,
    pickup_location_id,
    dropoff_location_id,
    license_number,
    requested_at,
    pickup_at,
    dropoff_at,
    trip_miles,
    trip_duration_seconds,
    base_passenger_fare,
    tolls,
    black_car_fund_fee,
    sales_tax,
    congestion_surcharge,
    airport_fee,
    cbd_congestion_fee,
    tips,
    driver_pay,
    is_shared_ride_requested,
    is_shared_ride_matched,
    is_access_a_ride,
    is_wheelchair_requested,
    is_wheelchair_matched,
    base_passenger_fare < 0 as is_negative_fare
from trips