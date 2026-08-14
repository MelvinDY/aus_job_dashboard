# Migration: v1 (Azure SQL + pandas) → v2 (local SQL Server + dbt)

Evidence for PRD v2, FR-5: *"every KPI on every page compared against the
pre-migration export before the old `sql/` views are deleted."*

## What changed

| | v1 | v2 |
|---|---|---|
| Warehouse | Azure SQL, serverless, ~$2–6/month | SQL Server Developer in Docker, $0 |
| Cleaning / reshaping | `scripts/transform.py` (pandas) | `stg_labour_force` (dbt model) |
| Modelling | 5 wide staging tables + 8 hand-written views | star schema: `dim_date`, `dim_series`, `fct_labour_force` |
| Labels | dicts in Python | dbt seeds, under `accepted_values` tests |
| Tests | none | 124, run by `dbt build` |
| Report binding | `mart.v_*` on Azure SQL | `mart.v_*` on the local warehouse — same view names |

The mart layer kept v1's column contract exactly, which is why the Power BI
rebind was a connection-string change and not a report rewrite.

## How the check was run

Both sides were built from the **same ABS extract**, so any difference is the
port and not the data:

1. v1's `data/processed/*.csv` (pandas output) loaded into `staging.*` tables in
   a separate database, `aus_job_dashboard_v1`.
2. v1's `sql/staging/*.sql` and `sql/mart/*.sql` deployed on top, unmodified.
3. Every v1 mart compared against its dbt equivalent — row counts, column names
   and order, key sets, then every value column cell by cell.

## Result

| Mart | Rows | Columns | Keys | Values |
|---|---|---|---|---|
| `v_national_overview` | 580 = 580 | 11, same order | identical | **all identical** |
| `v_unemployment_by_state` | 4,640 = 4,640 | 9, same order | identical | **all identical** |
| `v_fulltime_parttime` | 1,740 = 1,740 | 11, same order | identical | **all identical** |
| `v_industry_breakdown` | 494 = 494 | 10, same order | identical | 1 of 8 columns differs on 2 rows |

**Every number displayed on every page of the report is unchanged.**

### The one difference, and why v2 is right

`v_industry_breakdown.employed_yoy_change_pct` differs on 2 of 494 rows, by 0.01
each. It is not a rounding-mode artifact — v1 computed the percentage from an
already-rounded numerator:

```python
# transform.py (v1)
df["employed_yoy_change_thousands"] = diff.round(3)          # rounded here
df["employed_yoy_change_pct"] = (
    df["employed_yoy_change_thousands"] / prev * 100         # then divided
)
```

v2 divides the unrounded change by the unrounded base.

| Row | Exact value | v1 | v2 |
|---|---|---|---|
| Electricity, Gas, Water & Waste — 1998 | 3.864768…% | 3.87 | **3.86** |
| Mining — 2007 | 8.865067…% | 8.86 | **8.87** |

v1 is wrong on both. Rounding the numerator to three decimals before dividing
was incidental, not intended — the metric is *change ÷ base*, and that is what
v2 computes.

Per PRD non-goal 4 the models are not bent back to reproduce a defect. In this
case nothing downstream had to be corrected either: both rows carry
`is_latest_year = 0` and `is_focus_industry = 0`, and every visual on the
Industry page filters to one or the other, so neither row was ever displayed.

### Headline finding

Unchanged and still the strongest number in the project — around **80% of
employed men work full-time against about 57% of employed women**.

## Coverage and vintage, restated

Two data-quality caveats survive the migration and are now enforced rather than
remembered:

- **All eight jurisdictions are present.** The ABS publishes no seasonally
  adjusted series for NT or ACT, and a request for all eight on that basis
  returns six with HTTP 200 and no warning. The state page therefore uses the
  **Trend** basis, which exists for all eight, so the ranking compares like with
  like. `assert_all_jurisdictions_present` and
  `assert_no_mixed_adjustment_types` fail the build if either property breaks.
- **Industry data is annual and lags.** The Labour Force survey has no industry
  dimension, so industry comes from the annual Labour Account, which is
  published years behind. Every title on that page states the vintage.

## Retired in this migration

Replaced by dbt models and removed once the check above passed:

- `sql/staging/*.sql`, `sql/mart/*.sql`, `sql/00_schemas.sql`
- `scripts/transform.py` — cleaning and typing now live in `stg_labour_force`
- `scripts/load.py` — superseded by `scripts/load_raw.py`, which lands the ABS
  response verbatim instead of a pandas-reshaped copy
- `scripts/deploy_views.py`, `scripts/check_views.py` — `dbt build` does both

All remain in git history, so the comparison above can be reconstructed.
