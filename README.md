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

### 5. Connect Power BI

See [`powerbi/SETUP.md`](powerbi/SETUP.md) for the full step-by-step guide.

Short version:

1. Open Power BI Desktop
2. For each file in `powerbi/queries/`, go to **Home > Transform Data > New Source > Blank Query > Advanced Editor** and paste the `.m` script (replace `<your-server>` and `<your-database>`)
3. **Model view** — mark `DateTable[date]` as the date table; connect it to the date column in each fact query
4. Add DAX measures from `powerbi/dax/measures.dax` into a blank `Measures` table
5. Build the 4 report pages using the visual specs in `powerbi/SETUP.md`
6. Export to PDF: **File > Export > Export to PDF**

---

## Project Structure

```
aus_job_dashboard/
├── scripts/
│   ├── extract.py          # Download from ABS Data API
│   ├── transform.py        # Clean and reshape with Pandas
│   └── load.py             # Load into Azure SQL via SQLAlchemy
├── sql/
│   ├── 00_schemas.sql      # Create staging + mart schemas
│   ├── deploy_views.sql    # Run all views in order
│   ├── staging/            # 4 staging views
│   └── mart/               # 4 mart views
├── powerbi/
│   ├── SETUP.md            # Full Power BI setup guide
│   ├── queries/            # Power Query M scripts (one per mart view + date table)
│   └── dax/                # DAX measures for all 4 report pages
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
