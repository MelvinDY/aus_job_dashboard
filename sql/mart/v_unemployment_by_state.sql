-- mart.v_unemployment_by_state
-- Dashboard page: State Breakdown
-- Unemployment rate and employed persons per state over time,
-- with MoM and YoY changes for map/bar chart tooltips.
-- Power BI usage: map visual (latest month), bar chart (compare states), line chart (trend)

CREATE OR ALTER VIEW mart.v_unemployment_by_state AS

with latest_month as (
    select max(date) as max_date
    from staging.v_state_summary
),

state_data as (
    select
        s.date,
        s.region_code,
        s.region_name,
        round(s.employed_thousands,        1) as employed_thousands,
        round(s.unemployment_rate_pct,     2) as unemployment_rate_pct,
        s.unemployment_rate_mom_change_ppt,
        s.unemployment_rate_yoy_change_ppt,
        s.employed_yoy_change_pct,
        case when s.date = l.max_date then 1 else 0 end as is_latest_month
    from staging.v_state_summary  s
    cross join latest_month        l
)

select * from state_data;
GO
