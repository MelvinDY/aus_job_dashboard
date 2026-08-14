{{
    config(
        materialized = 'view',
        alias = 'v_industry_breakdown'
    )
}}

/*
    mart.v_industry_breakdown — Industry View page.

    Grain: (date, industry_code) — one row per ANZSIC division per year.

    Series: Australian Labour Account, employed persons (M9), Australia,
    ANZSIC division level only.

    VINTAGE WARNING, and it is the honest kind. This page is ANNUAL and its
    latest period is years behind every other page, which are monthly and
    current. That is not a bug in the pipeline: the ABS Labour Force survey has
    no industry dimension at all, so industry has to come from the Labour
    Account, which is annual and published with a long lag. Verified against the
    live API, not inferred from a stale file on disk.

    It stays in the report, labelled with its vintage on every title, rather
    than being quietly dropped or presented as current. Making the vintage a
    tested property is the point of the industry_data_vintage note below: the
    "employed" figures here are jobs-based Labour Account estimates and are not
    comparable with the survey numbers on the other three pages.

    The Labour Account also publishes sub-division codes. Only the 19 divisions
    are kept, and the TOTAL rollup is excluded so nothing sums the total in
    alongside its own components.
*/

with industry as (

    select
        f.date_key as date,
        d.industry_code,
        d.industry_name,
        d.is_focus_industry,
        max(f.obs_value) as employed_thousands

    from {{ ref('fct_labour_force') }} f
    inner join {{ ref('dim_series') }} d on d.series_id = f.series_id

    where d.source_dataflow        = 'ABS_LABOUR_ACCT'
      and d.measure_code           = 'M9'    -- Employed persons (jobs-based)
      and d.region_code            = 'AUS'
      and d.is_industry_division   = 1       -- divisions only; excludes TOTAL

    group by f.date_key, d.industry_code, d.industry_name, d.is_focus_industry

),

with_lag as (

    select
        *,
        -- Annual series, so the previous row IS the previous year.
        lag(employed_thousands, 1) over (
            partition by industry_code order by date
        ) as employed_prev_year
    from industry

),

changes as (

    select
        date,
        industry_code,
        industry_name,
        is_focus_industry,
        employed_thousands,
        round(employed_thousands - employed_prev_year, 3)
            as employed_yoy_change_thousands,
        round((employed_thousands - employed_prev_year)
              / nullif(employed_prev_year, 0) * 100, 2)
            as employed_yoy_change_pct,
        -- Ranked on the unrounded value, before presentation rounding can
        -- create ties that do not exist in the data.
        rank() over (partition by date order by employed_thousands desc)
            as rank_by_employment
    from with_lag

)

select
    date,
    industry_code,
    industry_name,

    round(employed_thousands,            1) as employed_thousands,
    round(employed_yoy_change_thousands, 1) as employed_yoy_change_thousands,
    round(employed_yoy_change_pct,       2) as employed_yoy_change_pct,
    rank_by_employment,

    -- Growth classification on the year-on-year percentage change.
    case
        when employed_yoy_change_pct >=  2.0 then 'Growing'
        when employed_yoy_change_pct <= -2.0 then 'Shrinking'
        else 'Stable'
    end as growth_category,

    case when date = max(date) over () then 1 else 0 end as is_latest_year,
    is_focus_industry

from changes
