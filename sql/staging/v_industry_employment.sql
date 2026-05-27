-- staging.v_industry_employment
-- Clean view over the industry_employment staging table.
-- Excludes the TOTAL row so mart views can add it back selectively.
-- Consumed by: mart.v_industry_breakdown, mart.v_employment_growth_yoy

CREATE OR ALTER VIEW staging.v_industry_employment AS

select
    date,
    industry_code,
    industry_name,
    employed_thousands,
    employed_yoy_change_thousands,
    employed_yoy_change_pct,

    -- rank industries by employment size within each year (for charts)
    rank() over (partition by date order by employed_thousands desc)
        as rank_by_employment

from staging.industry_employment
where
    date           is not null
    and industry_code not in ('TOTAL')   -- total kept out; use mart.v_national_overview for totals
    and employed_thousands is not null;
GO
