-- staging.v_state_summary
-- Clean view over the state_summary staging table.
-- Adds MoM and YoY unemployment rate changes per state.
-- Consumed by: mart.v_unemployment_by_state

CREATE OR ALTER VIEW staging.v_state_summary AS

with base as (
    select
        date,
        region_code,
        region_name,
        employed_thousands,
        unemployment_rate_pct
    from staging.state_summary
    where
        date                  is not null
        and region_code       is not null
        and unemployment_rate_pct is not null
),

with_lag as (
    select
        *,
        lag(unemployment_rate_pct, 1)  over (partition by region_code order by date)
            as unemployment_rate_prev_month,
        lag(unemployment_rate_pct, 12) over (partition by region_code order by date)
            as unemployment_rate_prev_year,
        lag(employed_thousands,    12) over (partition by region_code order by date)
            as employed_prev_year
    from base
)

select
    date,
    region_code,
    region_name,
    employed_thousands,
    unemployment_rate_pct,

    round(unemployment_rate_pct - unemployment_rate_prev_month, 3)
        as unemployment_rate_mom_change_ppt,
    round(unemployment_rate_pct - unemployment_rate_prev_year,  3)
        as unemployment_rate_yoy_change_ppt,
    round(
        (employed_thousands - employed_prev_year) / nullif(employed_prev_year, 0) * 100, 2
    ) as employed_yoy_change_pct

from with_lag;
GO
