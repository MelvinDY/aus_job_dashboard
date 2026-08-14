{{
    config(
        materialized = 'view',
        alias = 'v_fulltime_parttime'
    )
}}

/*
    mart.v_fulltime_parttime — Full-time vs Part-time page.

    Grain: (date, sex_code) — one row per sex per month.

    Series: Labour Force survey, 15+, seasonally adjusted, Australia,
    for Male, Female and Persons.

    Persons is a TOTAL, not a third category: Persons = Male + Female. Anything
    that aggregates all three rows double-counts, which is exactly what the
    v1 stacked area chart did before it was filtered to Persons. The column is
    kept (the page compares male and female shares — the headline finding of the
    whole project) but every consumer has to pick one level and say so.

    Shares are rounded before the year-on-year delta is taken, matching v1,
    where the share was computed and rounded in pandas before SQL differenced it.
*/

with ftpt as (

    select
        f.date_key as date,
        d.sex_code,
        d.sex_name as sex_label,
        max(case when d.measure_code = 'M1' then f.obs_value end) as employed_fulltime_thousands,
        max(case when d.measure_code = 'M2' then f.obs_value end) as employed_parttime_thousands,
        max(case when d.measure_code = 'M3' then f.obs_value end) as employed_total_thousands

    from {{ ref('fct_labour_force') }} f
    inner join {{ ref('dim_series') }} d on d.series_id = f.series_id

    where d.source_dataflow = 'LF'
      and d.region_code     = 'AUS'
      and d.age_code        = '1599'   -- 15 years and over
      and d.tsest_code      = '20'     -- Seasonally adjusted
      and d.measure_code in ('M1', 'M2', 'M3')

    group by f.date_key, d.sex_code, d.sex_name

),

shares as (

    select
        date,
        sex_code,
        sex_label,
        employed_fulltime_thousands,
        employed_parttime_thousands,
        employed_total_thousands,
        round(employed_fulltime_thousands / nullif(employed_total_thousands, 0) * 100, 2)
            as fulltime_share_pct,
        round(employed_parttime_thousands / nullif(employed_total_thousands, 0) * 100, 2)
            as parttime_share_pct
    from ftpt
    where employed_total_thousands is not null

),

with_lag as (

    select
        *,
        lag(fulltime_share_pct, 12) over (partition by sex_code order by date)
            as fulltime_share_prev_year,
        lag(employed_total_thousands, 12) over (partition by sex_code order by date)
            as employed_total_prev_year
    from shares

)

select
    date,
    sex_code,
    sex_label,

    round(employed_fulltime_thousands, 1) as employed_fulltime_thousands,
    round(employed_parttime_thousands, 1) as employed_parttime_thousands,
    round(employed_total_thousands,    1) as employed_total_thousands,
    round(fulltime_share_pct,          2) as fulltime_share_pct,
    round(parttime_share_pct,          2) as parttime_share_pct,

    round(fulltime_share_pct - fulltime_share_prev_year, 3)
        as fulltime_share_yoy_change_ppt,
    round((employed_total_thousands - employed_total_prev_year)
          / nullif(employed_total_prev_year, 0) * 100, 2)
        as employed_total_yoy_change_pct,

    case when date = max(date) over () then 1 else 0 end as is_latest_month

from with_lag
