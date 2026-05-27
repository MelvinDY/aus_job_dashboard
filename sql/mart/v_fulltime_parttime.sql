-- mart.v_fulltime_parttime
-- Dashboard page: Full-time vs Part-time
-- Employment type trend over time split by sex.
-- Power BI usage: stacked area / line chart (trend), bar chart (FT vs PT share by sex)

CREATE OR ALTER VIEW mart.v_fulltime_parttime AS

with latest_month as (
    select max(date) as max_date
    from staging.v_fulltime_parttime
)

select
    f.date,
    f.sex_code,
    f.sex_label,

    round(f.employed_fulltime_thousands,  1) as employed_fulltime_thousands,
    round(f.employed_parttime_thousands,  1) as employed_parttime_thousands,
    round(f.employed_total_thousands,     1) as employed_total_thousands,
    round(f.fulltime_share_pct,           2) as fulltime_share_pct,
    round(f.parttime_share_pct,           2) as parttime_share_pct,
    f.fulltime_share_yoy_change_ppt,
    f.employed_total_yoy_change_pct,

    case when f.date = l.max_date then 1 else 0 end as is_latest_month

from staging.v_fulltime_parttime f
cross join latest_month l;
GO
