{{
    config(
        materialized = 'view',
        alias = 'v_unemployment_by_state'
    )
}}

/*
    mart.v_unemployment_by_state — State Breakdown page.

    Grain: (date, region_code) — one row per state or territory per month.

    Series: Labour Force survey, Persons, 15+, TREND, states and territories 1-8.

    Trend, not seasonally adjusted, and that is the single most important
    decision in this model. The ABS does not publish a seasonally adjusted
    series for the Northern Territory or the ACT — their survey samples are too
    small to adjust — so a request for all eight jurisdictions on a seasonally
    adjusted basis returns six, with a 200 OK and no warning. v1 shipped a map
    of Australia missing two territories for exactly that reason.

    Trend exists for all eight, which puts every jurisdiction on one comparable
    basis. That matters because this page ranks states against each other, and
    ranking six adjusted numbers against two unadjusted ones is not a ranking.
    The cost is that these figures will not match the seasonally adjusted
    headline rate quoted in the news — the page says so, and
    assert_no_mixed_adjustment_types stops the mixture ever coming back.
*/

with state_measures as (

    select
        f.date_key    as date,
        d.region_code,
        d.region_name,
        max(case when d.measure_code = 'M3'  then f.obs_value end) as employed_thousands,
        max(case when d.measure_code = 'M13' then f.obs_value end) as unemployment_rate_pct

    from {{ ref('fct_labour_force') }} f
    inner join {{ ref('dim_series') }} d on d.series_id = f.series_id

    where d.source_dataflow  = 'LF'
      and d.geography_level in ('State', 'Territory')
      and d.sex_code         = '3'      -- Persons
      and d.age_code         = '1599'   -- 15 years and over
      and d.tsest_code       = '30'     -- Trend: the only basis all 8 publish
      and d.measure_code in ('M3', 'M13')

    group by f.date_key, d.region_code, d.region_name

),

filtered as (

    select *
    from state_measures
    where unemployment_rate_pct is not null

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
    from filtered

)

select
    date,
    region_code,
    region_name,

    round(employed_thousands,    1) as employed_thousands,
    round(unemployment_rate_pct, 2) as unemployment_rate_pct,

    round(unemployment_rate_pct - unemployment_rate_prev_month, 3)
        as unemployment_rate_mom_change_ppt,
    round(unemployment_rate_pct - unemployment_rate_prev_year, 3)
        as unemployment_rate_yoy_change_ppt,
    round((employed_thousands - employed_prev_year)
          / nullif(employed_prev_year, 0) * 100, 2)
        as employed_yoy_change_pct,

    case when date = max(date) over () then 1 else 0 end as is_latest_month

from with_lag
