-- Date dimension: one row per calendar day from 2024-01-01 to 2025-12-31 (731 rows).
-- Generated in SQL (no source table, 0 bytes read). Includes days without trips,
-- so reports can show them as zero instead of skipping them.
-- fct_trips joins on date(pickup_at) = date_day.

with date_spine as (
    select date_day
    from unnest(generate_date_array('2024-01-01', '2025-12-31')) as date_day
)

select
    date_day,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month,
    format_date('%B', date_day) as month_name,
    extract(day from date_day) as day_of_month,
    extract(dayofweek from date_day) as day_of_week, -- 1 = Sunday ... 7 = Saturday
    format_date('%A', date_day) as day_name,
    extract(week from date_day) as week_of_year,
    extract(dayofweek from date_day) in (1, 7) as is_weekend,
    format_date('%Y-%m', date_day) as year_month
from date_spine