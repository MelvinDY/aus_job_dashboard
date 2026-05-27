# Power BI Setup Guide

## Prerequisites
- Power BI Desktop installed (free from microsoft.com/en-us/power-bi)
- Azure SQL loaded — run `load.py` and `deploy_views.sql` first
- Your Azure SQL server name and database name

---

## Step 1 — Connect to Azure SQL (4 queries)

For each query below:

1. Open Power BI Desktop → **Home > Get Data > Azure > Azure SQL Database**
2. Server: `<your-server>.database.windows.net`
3. Database: `<your-database>`
4. Data Connectivity mode: **Import**
5. Click **Advanced options** → paste the SQL from the relevant `.m` file
6. Sign in with your Azure credentials when prompted

Alternatively, use the Power Query M scripts directly:

1. **Home > Transform Data** to open Power Query Editor
2. **Home > New Source > Blank Query**
3. **View > Advanced Editor** — paste the full contents of each `.m` file
4. Rename the query to match the comment at the top of each file

**Queries to add (in order):**

| File | Query name | Mart view |
|---|---|---|
| `queries/national_overview.m` | `NationalOverview` | `mart.v_national_overview` |
| `queries/unemployment_by_state.m` | `UnemploymentByState` | `mart.v_unemployment_by_state` |
| `queries/industry_breakdown.m` | `IndustryBreakdown` | `mart.v_industry_breakdown` |
| `queries/fulltime_parttime.m` | `FulltimeParttime` | `mart.v_fulltime_parttime` |
| `queries/date_table.m` | `DateTable` | _(calculated, no SQL)_ |

> Replace `<your-server>` and `<your-database>` in each `.m` file before pasting.

---

## Step 2 — Mark the Date Table

1. In Report view, select **DateTable** in the Fields pane
2. Right-click → **Mark as date table**
3. Select `date` as the date column → OK

---

## Step 3 — Create Relationships

In **Model view**, create these relationships (all one-to-many, single direction):

| From (one side) | To (many side) | On column |
|---|---|---|
| `DateTable[date]` | `NationalOverview[date]` | date |
| `DateTable[date]` | `UnemploymentByState[date]` | date |
| `DateTable[date]` | `FulltimeParttime[date]` | date |

> IndustryBreakdown uses annual dates (Jan 1 each year) — connect to DateTable the same way. Use `is_first_of_month = 1` as a filter in visuals that mix monthly and annual data.

---

## Step 4 — Add DAX Measures

1. **Home > Enter Data** → create a table called `Measures` with one blank column → Load
2. Select the `Measures` table in the Fields pane
3. **Modelling > New Measure** → paste each formula from `dax/measures.dax`

---

## Step 5 — Build Report Pages

### Page 1 — Overview

| Visual | Fields | Notes |
|---|---|---|
| Line chart | X: `DateTable[date]`, Y: `NationalOverview[unemployment_rate_pct]` | Add trend line in Analytics pane |
| KPI card | Value: `[Latest Unemployment Rate]`, Goal: prev year | Subtitle: `[Unemployment Rate Subtitle]` |
| KPI card | Value: `[Latest Employed Thousands]` | Subtitle: `[Employed Subtitle]` |
| KPI card | Value: `[Latest Participation Rate]` | No goal needed |

### Page 2 — State Breakdown

| Visual | Fields | Notes |
|---|---|---|
| Map | Location: `UnemploymentByState[region_name]`, Bubble size: `[Selected State Unemployment Rate]` | Set map style to Light |
| Bar chart (sorted) | Axis: `region_name`, Value: `unemployment_rate_pct` | Add constant line: `[National Avg Unemployment Rate]` |
| Line chart | X: `date`, Y: `unemployment_rate_pct`, Legend: `region_name` | Filter to last 5 years for readability |

### Page 3 — Industry View

| Visual | Fields | Notes |
|---|---|---|
| Horizontal bar | Y: `industry_name`, X: `employed_thousands` | Filter: `is_latest_year = 1`, sort descending |
| Line chart | X: `date`, Y: `employed_thousands`, Legend: `industry_name` | Filter: `is_focus_industry = 1` |
| Matrix | Rows: `industry_name`, Cols: `date` (years), Values: `[Industry YoY Change Label]` | Conditional formatting: green/red |

### Page 4 — Full-time vs Part-time

| Visual | Fields | Notes |
|---|---|---|
| Stacked area | X: `date`, Y: FT + PT thousands, Legend: sex_label | Filter: `sex_label = Persons` |
| Line chart | X: `date`, Y: `fulltime_share_pct`, Legend: `sex_label` | Shows gender gap over time |
| KPI card | Value: `[Latest FT Share Persons]` | Subtitle: `[FT Share Subtitle]` |
| KPI card | Value: `[Latest PT Share Persons]` | |

---

## Step 6 — Publish

1. **File > Save As** → save as `aus_job_dashboard.pbix` in the `powerbi/` folder
2. `.pbix` is gitignored (binary file, too large)
3. **File > Export > Export to PDF** → save as `powerbi/dashboard_export.pdf` → commit this
4. Share the PDF link in your portfolio at `melvindy.vercel.app/projects/data`
