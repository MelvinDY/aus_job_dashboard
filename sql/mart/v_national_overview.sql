-- mart.v_national_overview
-- Dashboard page: Overview
-- Provides the national unemployment trend line, employed persons KPI,
-- and participation rate KPI — with MoM and YoY context.
-- Power BI usage: line chart (unemployment trend), KPI cards (latest month)

CREATE OR ALTER VIEW mart.v_national_overview AS

select
    date,

    -- Core KPIs
    round(employed_thousands,        1) as employed_thousands,
    round(unemployed_thousands,      1) as unemployed_thousands,
    round(unemployment_rate_pct,     2) as unemployment_rate_pct,
    round(participation_rate_pct,    2) as participation_rate_pct,
    round(emp_to_pop_ratio_pct,      2) as emp_to_pop_ratio_pct,

    -- MoM change (for KPI card sub-text)
    unemployment_rate_mom_change_ppt,
    employed_mom_change_pct,

    -- YoY change (for trend context)
    unemployment_rate_yoy_change_ppt,
    employed_yoy_change_pct,

    -- Flag to identify the latest available month (for default KPI card values)
    case
        when date = max(date) over () then 1 else 0
    end as is_latest_month

from staging.v_national_summary;
GO
