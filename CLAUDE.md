# Australian Labour Market Analytics Dashboard — PRD for Claude Code

## Project Overview

An end-to-end data analytics portfolio project for Melvin Darial Yogiana. It ingests real
Australian Bureau of Statistics (ABS) Labour Force survey data, cleans and loads it into
Azure SQL, transforms it with SQL views, and visualises it in Power BI. The pipeline mirrors
the Azure SQL environment used professionally at Foresight Analytics.

**Goal:** Demonstrate the full analyst stack (ingest → transform → visualise) using real
government data, suitable for linking on a data portfolio at melvindy.vercel.app/projects/data.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Data source | ABS Labour Force CSV/Excel (abs.gov.au) — no API key required |
| Ingestion & cleaning | Python 3, Pandas |
| Database connector | pyodbc or SQLAlchemy |
| Database | Azure SQL |
| Transformation | SQL views (staging → mart pattern) |
| Visualisation | Power BI Desktop |
| Version control | GitHub |

---

## Repository Structure

```
aus_job_dashboard/
├── CLAUDE.md               # This file — project spec for Claude Code
├── README.md               # Public-facing docs for GitHub
├── .gitignore
├── data/
│   ├── raw/                # Downloaded ABS files (never committed — gitignored)
│   └── processed/          # Cleaned CSVs ready for upload (gitignored)
├── scripts/
│   ├── extract.py          # Download ABS Labour Force data
│   ├── transform.py        # Pandas cleaning: fix headers, reshape wide → long
│   └── load.py             # Load processed data into Azure SQL via pyodbc/SQLAlchemy
└── sql/
    ├── staging/            # Raw-to-staging views
    └── mart/               # Mart views consumed by Power BI
```

---

## Pipeline Steps

### Step 1 — Data Extraction (`scripts/extract.py`)
- Download the monthly ABS Labour Force dataset (CSV/Excel) from abs.gov.au
- Store raw files in `data/raw/` (gitignored)
- Target tables: unemployment rate, employment by industry, full-time vs part-time, state breakdowns

### Step 2 — Clean & Transform with Python (`scripts/transform.py`)
- Fix messy ABS headers (multi-row headers, merged cells)
- Reshape from wide format to long format (date | metric | value | state | industry)
- Output cleaned CSVs to `data/processed/`

### Step 3 — Load to Azure SQL (`scripts/load.py`)
- Use `pyodbc` or `SQLAlchemy` to connect to Azure SQL
- Load processed DataFrames into staging tables
- Connection string pulled from environment variable `AZURE_SQL_CONN_STR` — never hardcode credentials

### Step 4 — SQL Views (`sql/staging/` and `sql/mart/`)
- **Staging views:** clean column aliasing, data-type casting, deduplication
- **Mart views (key metrics):**
  - `mart_unemployment_by_state` — unemployment rate per state over time
  - `mart_employment_growth_yoy` — YoY employment growth by industry
  - `mart_industry_breakdown` — sector-level employed persons trend
  - `mart_fulltime_parttime` — full-time vs part-time split by gender over time

### Step 5 — Power BI (`/powerbi/`)
- Connect Power BI Desktop to Azure SQL using native connector
- Point queries at mart views only
- Add a date table for time intelligence (MoM, YoY)
- Build 4 report pages (see Dashboard Pages below)
- Export final dashboard as PDF and commit to repo

---

## Dashboard Pages

| Page | Content |
|---|---|
| Overview | National unemployment rate trend line, total employed persons KPI card, participation rate KPI card |
| State Breakdown | Map visual + bar chart — NSW, VIC, QLD, WA, SA, TAS, ACT, NT |
| Industry View | Sector employment trend — tech, healthcare, retail, construction (growing vs shrinking) |
| Full-time vs Part-time | Employment type over time, split by gender |

---

## Environment Variables

Store these in a `.env` file (gitignored) and load with `python-dotenv`:

```
AZURE_SQL_CONN_STR=Driver={ODBC Driver 18 for SQL Server};Server=...;Database=...;Uid=...;Pwd=...
```

---

## Coding Conventions

- Python: PEP 8, functions over scripts, no hardcoded credentials
- SQL: lowercase keywords, snake_case identifiers, explicit column lists (no `SELECT *` in mart views)
- Each script should be runnable standalone: `python scripts/extract.py`
- Use `requirements.txt` to pin dependencies

---

## Definition of Done

- [ ] ABS data downloaded and cleaned by Python scripts
- [ ] Data loaded into Azure SQL staging tables
- [ ] All 4 mart views written and tested
- [ ] Power BI report connected to mart views with all 4 pages built
- [ ] Dashboard exported as PDF in repo
- [ ] README complete with setup instructions and screenshot
- [ ] Repo pushed to GitHub and linked on portfolio site
