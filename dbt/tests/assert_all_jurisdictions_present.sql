/*
    Australia has eight states and territories. The state page must contain all
    eight, in every month it reports.

    The companion to assert_no_mixed_adjustment_types. That test catches the
    wrong fix for the NT/ACT gap (back-filling with a different series type);
    this one catches the gap itself. accepted_values on region_name can only
    catch a member that should not be there — it passes happily on a map of
    Australia with two territories missing, which is precisely the bug that
    shipped in v1 and was not noticed for weeks.

    Fails on any month that does not carry all eight jurisdictions.
*/

with per_month as (

    select
        date,
        count(distinct region_code) as jurisdictions
    from {{ ref('v_unemployment_by_state') }}
    group by date

)

select
    date,
    jurisdictions,
    8 as jurisdictions_expected
from per_month
where jurisdictions <> 8
