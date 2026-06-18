# Australian Labour Market Analytics Dashboard

An end-to-end data analytics portfolio project — real ABS Labour Force data from the
Australian Bureau of Statistics, cleaned with Python, stored in Azure SQL, transformed
with SQL views, and visualised in Power BI.

**Stack:** Python · Pandas · Azure SQL · SQL Views · Power BI · GitHub

---

## Pipeline

```
ABS Data API  →  extract.py  →  transform.py  →  load.py  →  Azure SQL  →  Power BI
                 (data/raw)     (data/processed)  (staging tables)  (mart views)
```

## Dashboard Pages

| Page | Content |
|---|---|
| Overview | National unemployment rate trend, employed persons KPI, participation rate KPI |
| State Breakdown | Map + bar chart — unemployment rate and employed persons per state |
| Industry View | Sector employment trend with growing/shrinking classification |
| Full-time vs Part-time | Employment type split by gender over time |

![Dashboard — Overview page](powerbi/dashboard_overview.png)

> Full four-page export: **[powerbi/dashboard_export.pdf](powerbi/dashboard_export.pdf)**

---

## Prerequisites

- Python 3.9+
- [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- An Azure SQL database (free tier works)
- Power BI Desktop (free from microsoft.com/en-us/power-bi)

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/MelvinDY/aus_job_dashboard.git
cd aus_job_dashboard
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your Azure SQL connection string:

```
AZURE_SQL_CONN_STR=Driver={ODBC Driver 18 for SQL Server};Server=<your-server>.database.windows.net;Database=<your-db>;Uid=<username>;Pwd=<password>
```

### 3. Run the pipeline

Run the three scripts in order:

```bash
# Download ABS Labour Force data via the ABS Data API (no key required)
python scripts/extract.py

# Clean, reshape, and add calculated columns
python scripts/transform.py

# Load processed CSVs into Azure SQL staging tables
python scripts/load.py
```

**What each script does:**

| Script | Input | Output |
|---|---|---|
| `extract.py` | ABS Data API | `data/raw/*.csv` — 5 datasets, ~19k rows total |
| `transform.py` | `data/raw/` | `data/processed/*.csv` — cleaned, labelled, wide format |
| `load.py` | `data/processed/` | Azure SQL `staging.*` — 5 tables, truncate + reload |

### 4. Deploy SQL views

Open `sql/deploy_views.sql` in SSMS or Azure Data Studio and run it against your database.
This creates the `staging` and `mart` schemas and deploys all 9 views in dependency order.

**Staging views** (add MoM/YoY deltas via LAG):

| View | Source table |
|---|---|
| `staging.v_national_summary` | `staging.national_summary` |
| `staging.v_state_summary` | `staging.state_summary` |
| `staging.v_fulltime_parttime` | `staging.fulltime_parttime` |
| `staging.v_industry_employment` | `staging.industry_employment` |

**Mart views** (consumed by Power BI):

| View | Dashboard page |
|---|---|
| `mart.v_national_overview` | Overview |
| `mart.v_unemployment_by_state` | State Breakdown |
| `mart.v_industry_breakdown` | Industry View |
| `mart.v_fulltime_parttime` | Full-time vs Part-time |

### 5. Build the Power BI report

The report is generated as a `.pbip` (Power BI Project) file — Power BI's text-based,
version-controlled format. Power BI Desktop Nov 2022 or later is required.

**5a. Set your server and database**

Edit the two constants at the top of `powerbi/build_report.py`:

```python
SERVER   = "<your-server>.database.windows.net"
DATABASE = "<your-database>"
```

**5b. Generate the project files**

```bash
python powerbi/build_report.py
```

This writes five files:

| File | Purpose |
|---|---|
| `powerbi/aus_job_dashboard.pbip` | Project entry point — open this in Power BI Desktop |
| `powerbi/aus_job_dashboard.SemanticModel/model.bim` | Data model: 6 tables, 4 relationships, 15 DAX measures |
| `powerbi/aus_job_dashboard.Report/report.json` | Report: 4 pages, 25 visuals |

**5c. Open in Power BI Desktop**

1. Double-click `powerbi/aus_job_dashboard.pbip`
2. Sign in to Azure SQL when prompted
3. Click **Home > Refresh** to load data
4. Mark `DateTable` as the date table: right-click in Fields pane → **Mark as date table > Date**

**5d. Export and publish**

From Power BI Desktop: `File > Export > Export to PDF`.

Alternatively, regenerate the committed dashboard PDF and README screenshot
straight from the mart views (no Desktop GUI needed):

```bash
python scripts/export_dashboard.py
```

This renders the same four pages from `mart.*` to `powerbi/dashboard_export.pdf`
and `powerbi/dashboard_overview.png`. Commit them and link the PDF on your portfolio.

---

## Project Structure

```
aus_job_dashboard/
├── scripts/
│   ├── extract.py          # Download from ABS Data API
│   ├── transform.py        # Clean and reshape with Pandas
│   ├── load.py             # Load into Azure SQL via SQLAlchemy
│   ├── deploy_views.py     # Deploy all SQL views to Azure SQL
│   ├── check_views.py      # Verify deployed views
│   └── export_dashboard.py # Render the 4 dashboard pages to PDF + PNG
├── sql/
│   ├── 00_schemas.sql      # Create staging + mart schemas
│   ├── deploy_views.sql    # Run all views in order
│   ├── staging/            # 4 staging views
│   └── mart/               # 4 mart views
├── powerbi/
│   ├── build_report.py     # Generates the .pbip project — run this
│   ├── aus_job_dashboard.pbip             # Open in Power BI Desktop
│   ├── aus_job_dashboard.SemanticModel/   # model.bim — tables, relationships, measures
│   ├── aus_job_dashboard.Report/          # report.json — 4 pages, 25 visuals
│   ├── dashboard_export.pdf  # Exported 4-page dashboard
│   ├── dashboard_overview.png # Overview page (README screenshot)
│   ├── SETUP.md            # Manual setup guide (alternative to build_report.py)
│   ├── queries/            # Power Query M scripts
│   └── dax/                # DAX measures reference
├── data/
│   ├── raw/                # Downloaded ABS files (gitignored)
│   └── processed/          # Cleaned CSVs (gitignored)
├── .env.example
└── requirements.txt
```

---

## Data Source

[ABS Labour Force Survey](https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia)
— monthly, free, no API key required. Accessed via the
[ABS Data API](https://api.data.abs.gov.au) (`data.api.abs.gov.au/rest`).

Industry data from the
[ABS Labour Account Australia](https://www.abs.gov.au/statistics/labour/jobs/labour-account-australia)
— annual, national, ANZSIC division level.

---

## Portfolio

- Data portfolio: [melvindy.vercel.app/projects/data](https://melvindy.vercel.app/projects/data)
