{{
    config(
        materialized = 'table'
    )
}}

/*
    fct_labour_force — every ABS observation, once.

    Grain: (series_id, date_key) — one observation of one series in one period.

    Deliberately narrow. The measure is the ABS value and nothing else; what the
    value means (employed persons, a rate, full-time or part-time, which state,
    seasonally adjusted or trend) is an attribute of the series and lives in
    dim_series. That is what makes a single fact table able to carry the whole
    report: the four v1 tables were four different flattenings of these same
    rows.

    Rates and counts share a column, which is normal for this shape and is why
    dim_series.measure_unit exists: never sum across measures without filtering
    to one, or you will add percentages to thousands of people.
*/

select
    -- Surrogate key over the declared grain, so the uniqueness of that grain is
    -- a testable property of the table rather than a claim in a comment.
    s.series_id + '|' + convert(varchar(10), s.period_date, 23) as series_period_key,

    s.series_id,
    s.period_date as date_key,

    s.obs_value,

    -- Degenerate: which extract landed this row. Kept for lineage back to the
    -- specific API call, not for slicing.
    s.source_extract

from {{ ref('stg_labour_force') }} s
