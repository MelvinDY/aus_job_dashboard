{{
    config(
        materialized = 'table'
    )
}}

/*
    dim_date — the date dimension.

    Grain: (date_key), one row per month, first day of the month.

    Month grain because that is the finest grain the ABS publishes here: the
    Labour Force survey is monthly and the Labour Account is annual (landed on
    1 January, so it sits on the same dimension rather than needing a second
    one).

    The spine is generated across the full span of the fact rather than selected
    from it. Reading distinct dates out of a fact table gives you a dimension
    with holes wherever the data has holes, and then a month with no
    observations silently vanishes from a trend line instead of showing as a gap.
*/

with bounds as (

    select
        min(period_date) as min_period,
        max(period_date) as max_period
    from {{ ref('stg_labour_force') }}

),

-- A numbers list. sys.all_objects is the standard T-SQL way to get one without
-- a helper table, and it exists on SQL Server, Azure SQL and Fabric alike.
numbers as (

    select row_number() over (order by (select null)) - 1 as n
    from sys.all_objects

),

months as (

    select
        dateadd(month, n.n, b.min_period) as date_key
    from numbers n
    cross join bounds b
    where n.n <= datediff(month, b.min_period, b.max_period)

)

select
    date_key,

    year(date_key)    as year,
    month(date_key)   as month_number,

    -- Spelled out rather than DATENAME, which follows the session language and
    -- would quietly change these strings on a differently-configured server.
    case month(date_key)
        when 1 then 'Jan' when 2  then 'Feb' when 3  then 'Mar'
        when 4 then 'Apr' when 5  then 'May' when 6  then 'Jun'
        when 7 then 'Jul' when 8  then 'Aug' when 9  then 'Sep'
        when 10 then 'Oct' when 11 then 'Nov' when 12 then 'Dec'
    end as month_name,

    case month(date_key)
        when 1 then 'Jan' when 2  then 'Feb' when 3  then 'Mar'
        when 4 then 'Apr' when 5  then 'May' when 6  then 'Jun'
        when 7 then 'Jul' when 8  then 'Aug' when 9  then 'Sep'
        when 10 then 'Oct' when 11 then 'Nov' when 12 then 'Dec'
    end + ' ' + cast(year(date_key) as varchar(4)) as month_year,

    'Q' + cast(datepart(quarter, date_key) as varchar(1)) as quarter,
    datepart(quarter, date_key) as quarter_number,

    -- Australian financial year: July to June, named for the year it ends in.
    case
        when month(date_key) >= 7 then 'FY' + cast(year(date_key) + 1 as varchar(4))
        else 'FY' + cast(year(date_key) as varchar(4))
    end as financial_year

from months
