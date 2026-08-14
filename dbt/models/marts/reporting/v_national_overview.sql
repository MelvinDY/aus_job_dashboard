{{
    config(
        materialized = 'view',
        alias = 'v_national_overview'
    )
}}

/*
    mart.v_national_overview — Overview page.

    Grain: (date), one row per month.

    Series: Labour Force survey, Persons, 15+, seasonally adjusted, Australia.
    Seasonally adjusted is the right basis nationally — it is what the ABS
    headline rate and every news report quote — and it exists for Australia as a
    whole, which is the reason the state page has to use a different one.

    Column contract is v1's, unchanged, so the Power BI report rebinds without
    edits. The derivation order is v1's too: deltas are computed from unrounded
    values and only the presented figures are rounded, so a rounded number never
    feeds another calculation.
*/

with national_measures as (

    select
        f.date_key as date,
        max(case when d.measure_code = 'M3'  then f.obs_value end) as employed_thousands,
        max(case when d.measure_code = 'M6'  then f.obs_value end) as unemployed_thousands,
        max(case when d.measure_code = 'M12' then f.obs_value end) as participation_rate_pct,
        max(case when d.measure_code = 'M13' then f.obs_value end) as unemployment_rate_pct,
        max(case when d.measure_code = 'M16' then f.obs_value end) as emp_to_pop_ratio_pct

    from {{ ref('fct_labour_force') }} f
    inner join {{ ref('dim_series') }} d on d.series_id = f.series_id

    where d.source_dataflow = 'LF'
      and d.region_code     = 'AUS'
      and d.sex_code        = '3'      -- Persons
      and d.age_code        = '1599'   -- 15 years and over
      and d.tsest_code      = '20'     -- Seasonally adjusted
      and d.measure_code in ('M3', 'M6', 'M12', 'M13', 'M16')

    group by f.date_key

),

filtered as (

    select *
    from national_measures
    where employed_thousands    is not null
      and unemployment_rate_pct is not null

),

with_lag as (

    select
        *,
        lag(unemployment_rate_pct, 1)  over (order by date) as unemployment_rate_prev_month,
        lag(employed_thousands,    1)  over (order by date) as employed_prev_month,
        lag(unemployment_rate_pct, 12) over (order by date) as unemployment_rate_prev_year,
        lag(employed_thousands,    12) over (order by date) as employed_prev_year
    from filtered

)

select
    date,

    round(employed_thousands,     1) as employed_thousands,
    round(unemployed_thousands,   1) as unemployed_thousands,
    round(unemployment_rate_pct,  2) as unemployment_rate_pct,
    round(participation_rate_pct, 2) as participation_rate_pct,
    round(emp_to_pop_ratio_pct,   2) as emp_to_pop_ratio_pct,

    -- Month on month
    round(unemployment_rate_pct - unemployment_rate_prev_month, 3)
        as unemployment_rate_mom_change_ppt,
    round((employed_thousands - employed_prev_month)
          / nullif(employed_prev_month, 0) * 100, 2)
        as employed_mom_change_pct,

    -- Year on year
    round(unemployment_rate_pct - unemployment_rate_prev_year, 3)
        as unemployment_rate_yoy_change_ppt,
    round((employed_thousands - employed_prev_year)
          / nullif(employed_prev_year, 0) * 100, 2)
        as employed_yoy_change_pct,

    case when date = max(date) over () then 1 else 0 end as is_latest_month

from with_lag
