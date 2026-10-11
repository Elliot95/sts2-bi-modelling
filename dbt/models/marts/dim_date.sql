-- Grain: one row per calendar day. Generated here rather than seeded by
-- scripts/generate_dim_date.py, so the calendar is versioned and rebuilt with
-- everything else. Same range (2024-01-01 to Dec 31 three years ahead) and
-- conventions: day_of_week 1 = Sunday .. 7 = Saturday, ISO week number.
with days as (
    select d as date_key
    from unnest(generate_date_array(
        date '2024-01-01',
        date(extract(year from current_date()) + 3, 12, 31)
    )) as d
)

select
    date_key,
    extract(year from date_key)         as year,
    extract(quarter from date_key)      as quarter,
    extract(month from date_key)        as month,
    format_date('%B', date_key)         as month_name,
    extract(day from date_key)          as day,
    extract(dayofweek from date_key)    as day_of_week,
    format_date('%A', date_key)         as day_name,
    extract(isoweek from date_key)      as week_of_year,
    extract(dayofweek from date_key) in (1, 7) as is_weekend
from days
