/*
    The test the PRD asks for by name: no mart may mix adjustment types within
    one comparison.

    Why this is worth a test rather than a comment. The ABS publishes three
    types of series estimate — Original, Seasonally adjusted and Trend — and
    they are not interchangeable. It does NOT publish a seasonally adjusted
    series for the Northern Territory or the ACT, because those survey samples
    are too small to adjust. Ask the API for all eight jurisdictions seasonally
    adjusted and it returns six, with HTTP 200 and no warning: the response is
    the intersection of what you asked for and what exists.

    v1 shipped that. A state page that ranks jurisdictions against each other
    was quietly missing two of them, and the chart looked entirely normal. Had
    the gap been "fixed" by back-filling NT and ACT with Original estimates, the
    result would have been worse — a ranking of six adjusted numbers against two
    unadjusted ones, which is not a ranking of anything.

    So the property under test is: every series feeding a cross-jurisdiction
    comparison shares one adjustment type. The filter below deliberately mirrors
    v_unemployment_by_state's own series selection — if that mart's filter
    changes, this test has to be re-read and re-agreed, which is the point.

    Fails if the state comparison draws on more than one adjustment type.
*/

with state_comparison_series as (

    select distinct
        region_name,
        adjustment_type
    from {{ ref('dim_series') }}
    where source_dataflow   = 'LF'
      and geography_level  in ('State', 'Territory')
      and sex_code          = '3'      -- Persons
      and age_code          = '1599'   -- 15 years and over
      and tsest_code        = '30'     -- the basis v_unemployment_by_state uses
      and measure_code     in ('M3', 'M13')

)

select
    count(distinct adjustment_type) as distinct_adjustment_types,
    min(adjustment_type)            as an_adjustment_type,
    max(adjustment_type)            as another_adjustment_type
from state_comparison_series
having count(distinct adjustment_type) > 1
