-- mart.v_industry_breakdown
-- Dashboard page: Industry View
-- Employed persons by ANZSIC industry division over time.
-- Categorises each industry as Growing / Stable / Shrinking based on latest YoY change.
-- Power BI usage: bar chart (latest year), line chart (trend per industry), matrix

CREATE OR ALTER VIEW mart.v_industry_breakdown AS

with latest_year as (
    select max(date) as max_date
    from staging.v_industry_employment
),

classified as (
    select
        i.date,
        i.industry_code,
        i.industry_name,
        round(i.employed_thousands,              1) as employed_thousands,
        round(i.employed_yoy_change_thousands,   1) as employed_yoy_change_thousands,
        round(i.employed_yoy_change_pct,         2) as employed_yoy_change_pct,
        i.rank_by_employment,

        -- Growth classification based on YoY % change
        case
            when i.employed_yoy_change_pct >= 2.0  then 'Growing'
            when i.employed_yoy_change_pct <= -2.0 then 'Shrinking'
            else 'Stable'
        end as growth_category,

        case when i.date = l.max_date then 1 else 0 end as is_latest_year

    from staging.v_industry_employment i
    cross join latest_year l
),

-- Highlight the four industries called out in the project plan
focus_flag as (
    select
        *,
        case
            when industry_code in ('J', 'Q', 'G', 'E') then 1 else 0
        end as is_focus_industry
        -- J = Information Media & Telecommunications (tech proxy)
        -- Q = Health Care & Social Assistance
        -- G = Retail Trade
        -- E = Construction
    from classified
)

select * from focus_flag;
GO
