{{
    config(
        materialized = 'view'
    )
}}

/*
    stg_labour_force — every ABS observation, typed, keyed and deduplicated.

    Grain: (series_id, period_date)

    This model is the port of v1's transform.py. It does exactly what that
    script did — parse the period, coerce the value, drop empty observations —
    and nothing more. Reshaping, labelling and derivation moved out: labels are
    a dimension join, derived measures are reporting models, and both are tested.

    The two dataflows carry different dimensions, so they are unioned onto a
    common shape with the inapplicable ones left null:

      LF               MEASURE.SEX.AGE.TSEST.REGION.FREQ   (monthly, no industry)
      ABS_LABOUR_ACCT  MEASURE.ASGS_2016.LABOURACCT_IND.FREQ  (annual, no sex/adjustment)

    series_id is the ABS series key prefixed with its dataflow. It is the ABS's
    own identifier for a series rather than a hash, so a row in the fact can be
    traced straight back to an API call.
*/

with lf as (

    select
        -- The ABS series key: dataflow + every dimension, in the order the API
        -- documents it. Unique per series by construction.
        'LF.' + measure + '.' + sex + '.' + age + '.' + tsest + '.' + region + '.' + freq
            as series_id,
        'LF'            as source_dataflow,
        source_extract,
        measure         as measure_code,
        sex             as sex_code,
        age             as age_code,
        tsest           as tsest_code,
        region          as region_code,
        cast(null as varchar(20)) as industry_code,
        freq            as frequency_code,
        time_period,
        obs_value,
        unit_measure,
        unit_mult

    from {{ source('raw', 'lf_observations') }}

),

labour_account as (

    select
        'ABS_LABOUR_ACCT.' + measure + '.' + asgs_2016 + '.' + labouracct_ind + '.' + freq
            as series_id,
        'ABS_LABOUR_ACCT' as source_dataflow,
        source_extract,
        measure         as measure_code,
        cast(null as varchar(10)) as sex_code,
        cast(null as varchar(10)) as age_code,
        -- The Labour Account publishes no type-of-series-estimate dimension.
        -- Left null rather than guessed; dim_series renders it "Not applicable".
        cast(null as varchar(10)) as tsest_code,
        asgs_2016       as region_code,
        labouracct_ind  as industry_code,
        freq            as frequency_code,
        time_period,
        obs_value,
        unit_measure,
        unit_mult

    from {{ source('raw', 'labour_account_observations') }}

),

combined as (

    select * from lf
    union all
    select * from labour_account

),

typed as (

    select
        series_id,
        source_dataflow,
        source_extract,
        measure_code,
        sex_code,
        age_code,
        tsest_code,
        region_code,
        industry_code,
        frequency_code,

        -- ABS periods are 'YYYY-MM' monthly and 'YYYY' annual. Both become the
        -- first day of the period, which puts the annual Labour Account on the
        -- same month-grain date dimension as the monthly survey.
        case
            when len(time_period) = 4 then cast(time_period + '-01-01' as date)
            else cast(time_period + '-01' as date)
        end as period_date,

        time_period as source_period,
        cast(obs_value as float) as obs_value,
        unit_measure,
        unit_mult

    from combined
    -- The ABS publishes gaps as empty observations. They carry no information
    -- and would otherwise become nulls in the middle of every trend line.
    where obs_value is not null

),

deduplicated as (

    /*
        Several extracts request overlapping keys — national_summary and
        national_fulltime_parttime both pull M3 for Persons, seasonally
        adjusted, Australia — so the same ABS series arrives twice. The copies
        are identical (asserted by the assert_overlapping_extracts_agree test),
        so keeping either one is correct; the row_number just makes the choice
        deterministic.
    */
    select
        *,
        row_number() over (
            partition by series_id, period_date
            order by source_extract
        ) as _row_in_series_period
    from typed

)

select
    series_id,
    period_date,
    source_dataflow,
    source_extract,
    measure_code,
    sex_code,
    age_code,
    tsest_code,
    region_code,
    industry_code,
    frequency_code,
    source_period,
    obs_value,
    unit_measure,
    unit_mult

from deduplicated
where _row_in_series_period = 1
