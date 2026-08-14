/*
    Two extracts request overlapping ABS keys. national_summary asks for
    employed-total for Persons (M3, seasonally adjusted, Australia), and
    national_fulltime_parttime asks for the same series again as the denominator
    of its full-time share. The same series therefore lands in raw twice.

    stg_labour_force resolves that with a row_number and keeps one copy, which is
    only correct if the copies actually agree. This test is what makes that
    assumption safe: if the ABS ever revised a series between the two API calls
    in a single extract run, the deduplication would silently pick one revision
    and drop the other, and no other test in the project would notice.

    Compared on the raw layer, before deduplication, so it sees what staging
    threw away. Fails if any duplicated (series, period) has copies that differ.
*/

with raw_lf as (

    select
        'LF.' + measure + '.' + sex + '.' + age + '.' + tsest + '.' + region + '.' + freq
            as series_id,
        time_period,
        obs_value
    from {{ source('raw', 'lf_observations') }}
    where obs_value is not null

)

select
    series_id,
    time_period,
    count(*)                                as copies,
    min(obs_value)                          as lowest_value,
    max(obs_value)                          as highest_value,
    abs(max(obs_value) - min(obs_value))    as spread

from raw_lf
group by series_id, time_period
having count(*) > 1
   -- Float equality with a tolerance well below the data's precision: these are
   -- the same number from the same API, so any real difference is a revision.
   and abs(max(obs_value) - min(obs_value)) > 1e-9
