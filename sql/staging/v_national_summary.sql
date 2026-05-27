-- staging.v_national_summary
-- Clean view over the national_summary staging table.
-- Adds MoM and YoY deltas for key KPIs using LAG().
-- Consumed by: mart.v_national_overview

CREATE OR ALTER VIEW staging.v_national_summary AS

with base as (
    select
        date,
        employed_thousands,
        unemployed_thousands,
        participation_rate_pct,
        unemployment_rate_pct,
        emp_to_pop_ratio_pct
    from staging.national_summary
    where
        date        is not null
        and employed_thousands    is not null
        and unemployment_rate_pct is not null
),

with_lag as (
    select
        *,
        -- month-on-month deltas
        lag(unemployment_rate_pct, 1)  over (order by date) as unemployment_rate_prev_month,
        lag(employed_thousands,    1)  over (order by date) as employed_prev_month,
        -- year-on-year deltas (12 months back)
        lag(unemployment_rate_pct, 12) over (order by date) as unemployment_rate_prev_year,
        lag(employed_thousands,    12) over (order by date) as employed_prev_year
    from base
)

select
    date,
    employed_thousands,
    unemployed_thousands,
    participation_rate_pct,
    unemployment_rate_pct,
    emp_to_pop_ratio_pct,

    -- MoM
    round(unemployment_rate_pct - unemployment_rate_prev_month, 3)
        as unemployment_rate_mom_change_ppt,
    round(
        (employed_thousands - employed_prev_month) / nullif(employed_prev_month, 0) * 100, 2
    ) as employed_mom_change_pct,

    -- YoY
    round(unemployment_rate_pct - unemployment_rate_prev_year, 3)
        as unemployment_rate_yoy_change_ppt,
    round(
        (employed_thousands - employed_prev_year) / nullif(employed_prev_year, 0) * 100, 2
    ) as employed_yoy_change_pct

from with_lag;
GO
