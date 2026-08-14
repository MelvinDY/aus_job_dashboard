{{
    config(
        materialized = 'table'
    )
}}

/*
    dim_series — one row per ABS statistical series.

    Grain: (series_id)

    This is the dimension the project was missing. In v1 the attributes below
    were not modelled anywhere: they were encoded in the ABS series key, decoded
    by a dict in transform.py, and then flattened into four unrelated wide
    tables. Anything you wanted to slice by had to already be a column in the
    right table.

    Carrying `adjustment_type` here is the load-bearing part. The ABS does not
    publish a seasonally adjusted series for NT or ACT, so a state comparison
    built from "whatever came back" silently mixes adjusted and trend estimates
    — a chart that looks completely normal and is not comparable. With the
    attribute in a dimension, assert_no_mixed_adjustment_types can police it.
*/

with series as (

    select distinct
        series_id,
        source_dataflow,
        measure_code,
        sex_code,
        age_code,
        tsest_code,
        region_code,
        industry_code,
        frequency_code
    from {{ ref('stg_labour_force') }}

)

select
    s.series_id,
    s.source_dataflow,

    -- Measure and what it counts
    s.measure_code,
    m.measure_name,
    m.measure_unit,
    m.employment_type,

    -- Sex. Persons is a total, not a category: Persons = Male + Female, which
    -- is why summing all three double-counts (it did, in v1).
    s.sex_code,
    coalesce(x.sex_name, 'Not applicable') as sex_name,

    -- Type of series estimate
    s.tsest_code,
    coalesce(a.adjustment_type, 'Not applicable') as adjustment_type,
    coalesce(a.is_seasonally_adjusted, 0) as is_seasonally_adjusted,

    -- Geography
    s.region_code,
    coalesce(r.region_name, s.region_code) as region_name,
    coalesce(r.geography_level, 'Unknown') as geography_level,

    -- Industry. Null for the Labour Force survey, which has no industry
    -- dimension; populated only for the annual Labour Account.
    s.industry_code,
    coalesce(i.industry_name, s.industry_code) as industry_name,
    coalesce(i.is_division, 0) as is_industry_division,
    coalesce(i.is_focus_industry, 0) as is_focus_industry,

    -- Frequency
    s.frequency_code,
    case s.frequency_code
        when 'M' then 'Monthly'
        when 'A' then 'Annual'
        else 'Unknown'
    end as frequency,

    s.age_code

from series s
left join {{ ref('seed_measure') }}           m on m.measure_code   = s.measure_code
left join {{ ref('seed_sex') }}               x on x.sex_code       = s.sex_code
left join {{ ref('seed_adjustment_type') }}   a on a.tsest_code     = s.tsest_code
left join {{ ref('seed_region') }}            r on r.region_code    = s.region_code
left join {{ ref('seed_industry_division') }} i on i.industry_code  = s.industry_code
