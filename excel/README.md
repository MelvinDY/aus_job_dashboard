# Excel workbook — `aus_labour_market.xlsx`

An Excel deliverable driven by Power Query off the same mart the Power BI report
reads. Open it and everything is already populated; refresh it and it re-reads
the mart export.

## What is in it

| Sheet | What it shows |
|---|---|
| **Read me** | Source, refresh instructions, and the caveats below. Also holds the `DataFolder` cell that makes the refresh portable. |
| **National trend** | Monthly national series back to Feb 1978 — unemployment rate, employment, participation rate, plus month-on-month and year-on-year change. |
| **State comparison** | All eight states and territories for the latest month, ranked worst unemployment first. |
| **FT vs PT by sex** | Full-time / part-time split by sex, monthly, with the share of each. |
| **FT share pivot** | PivotTable of full-time share by year and sex, with a **Sex** slicer. This is the sheet carrying the headline finding. |

## How to refresh

**Data → Refresh All.** That is the whole procedure.

Excel may first show a yellow bar asking you to *Enable Content* — Power Query
connections are external connections, so this prompt is expected. It re-reads
the four CSVs in `excel/data/`, which the pipeline rewrites:

```
docker compose up -d
py -3 run_pipeline.py
```

`run_pipeline.py` finishes by exporting `mart.*` to `excel/data/*.csv`, so a
refresh after a pipeline run picks up the new figures. You do **not** need
Docker, SQL Server or a database driver just to open the workbook and refresh
it — the exports are committed to the repo.

### Why the refresh survives being cloned somewhere else

Power Query has no relative paths, so a workbook with someone's `C:\Users\...`
baked into it stops refreshing the moment anyone clones the repo elsewhere.
Instead, the named cell `DataFolder` on the **Read me** sheet holds:

```excel
=LEFT(CELL("filename",$A$1), FIND("[", CELL("filename",$A$1)) - 1) & "data\"
```

which resolves to the workbook's own folder when the file opens, and every query
reads its path from that cell. Move the repo anywhere and Refresh All still
works. Nothing to reconfigure.

### Query steps

Each query does: read the CSV → promote headers → set every column's type. Two
go further:

- **State comparison** — filters to `is_latest_month = 1`, sorts by
  unemployment rate descending, and keeps six columns. The ranking is part of
  the refresh, not a sort somebody applied by hand and will forget to redo.
- **Full-time vs part-time by sex** — adds a `year` column, which is what the
  PivotTable groups by.

To read them: **Data → Queries & Connections**, right-click a query → **Edit**.

## Two caveats worth reading before quoting a number

### 1. The state sheet is TREND, not seasonally adjusted

The ABS does not publish a seasonally adjusted series for the **Northern
Territory** or the **ACT** — those samples are too small to adjust. Ask the API
for all eight jurisdictions seasonally adjusted and it returns six, with HTTP
200 and no warning. An earlier version of this project shipped a state page
missing two territories for exactly that reason.

Trend estimates exist for all eight, so the sheet uses Trend throughout. That is
what makes ranking the jurisdictions against each other valid — six adjusted
numbers next to two unadjusted ones is not a ranking.

**The trade-off:** these rates will not match the seasonally adjusted headline
rate quoted in the news. That is expected, and is the correct trade for a
comparison. If you want the number the news quotes, use the **National trend**
sheet, which is seasonally adjusted.

A dbt test (`assert_no_mixed_adjustment_types`) fails the build if a comparison
ever mixes bases again, and another (`assert_all_jurisdictions_present`) fails
it if a jurisdiction goes missing.

### 2. "Persons" is a total, not a third category

On the **FT vs PT by sex** sheet, `Persons = Male + Female`. Summing all three
rows double-counts every number. Filter to one level before aggregating — the
PivotTable keeps them in separate columns for this reason.

## Rebuilding the workbook

The workbook is generated rather than hand-built, so it can be reproduced
instead of being a binary nobody can review:

```
py -3 scripts/build_workbook.py
```

That needs Excel installed (it drives it through COM) and only needs re-running
when the workbook's *structure* changes. Refreshing data does not require it.
