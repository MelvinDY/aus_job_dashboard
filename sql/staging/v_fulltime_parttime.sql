-- staging.v_fulltime_parttime
-- Clean view over the fulltime_parttime staging table.
-- Adds MoM change in FT/PT share per sex group.
-- Consumed by: mart.v_fulltime_parttime

CREATE OR ALTER VIEW staging.v_fulltime_parttime AS

with base as (
    select
        date,
        sex_code,
        sex_label,
        employed_fulltime_thousands,
        employed_parttime_thousands,
        employed_total_thousands,
        fulltime_share_pct,
        parttime_share_pct
    from staging.fulltime_parttime
    where
        date         is not null
        and sex_code is not null
        and employed_total_thousands is not null
)

select
    date,
    sex_code,
    sex_label,
    employed_fulltime_thousands,
    employed_parttime_thousands,
    employed_total_thousands,
    fulltime_share_pct,
    parttime_share_pct,

    round(
        fulltime_share_pct
        - lag(fulltime_share_pct, 12) over (partition by sex_code order by date), 3
    ) as fulltime_share_yoy_change_ppt,

    round(
        (employed_total_thousands
         - lag(employed_total_thousands, 12) over (partition by sex_code order by date))
        / nullif(lag(employed_total_thousands, 12) over (partition by sex_code order by date), 0) * 100
    , 2) as employed_total_yoy_change_pct

from base;
GO
