# Australian Labour Market Analytics Dashboard — PRD for the local toolchain

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
├── docs/engineering-notes.md               # This file — engineering notes
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

---

## Current Status & How to Continue (updated 2026-06-18)

### Environment gotchas (read first)
- **Python:** the bare `python` command is a Windows Store stub that fails. Use **`py -3`** (real interpreter at `…\Programs\Python\Python313\python.exe`).
- **Azure SQL is serverless and auto-pauses** after ~1h idle. First connection can take 60s+ to resume. `scripts/deploy_views.py` and `scripts/check_views.py` append `Connection Timeout=120` to handle this. To wake/verify the DB: `py -3 scripts/check_views.py`.
- **Server / DB:** `melvind.database.windows.net` / `aus_job_dashboard`. Credentials in `.env` (gitignored) work; firewall allows this machine.

### What's done
- Pipeline (extract → transform → load) run; `data/raw` + `data/processed` populated.
- Azure SQL loaded: 5 staging tables (~7,448 rows). 8 views deployed (4 staging + 4 mart); all 4 mart views execute and return rows (verified live).
- `scripts/deploy_views.py` / `check_views.py` deploy & verify views.
- `scripts/export_dashboard.py` renders the 4 dashboard pages from the **mart views** to `powerbi/dashboard_export.pdf` + `powerbi/dashboard_overview.png` (matplotlib; needs DB awake). README embeds the screenshot + links the PDF.
- Pushed to GitHub (`origin/master`).

### Power BI — SOURCE OF TRUTH
- **This file (docs/engineering-notes.md) governs the project** — spec, conventions, decisions, status, handoff. `build_report.py` only governs the generated `.pbip` files (`model.bim` / `report.json`); it is a build mechanism, not a competing authority. When they appear to disagree, docs/engineering-notes.md wins and gets updated.
- The `.pbip` is **generated** by `powerbi/build_report.py`. **Do NOT hand-edit `model.bim` / `report.json`** — edit `build_report.py` and regenerate: `py -3 powerbi/build_report.py`. (Hand-editing + Desktop re-saves previously corrupted the model into a state that wouldn't load.)
- After regenerating, **close Power BI Desktop without saving** before reopening `aus_job_dashboard.pbip`, or Desktop overwrites the regenerated files.
- Fixes already applied in `build_report.py`:
  1. DateTable DAX used `TEXT()` (Excel, not DAX) → replaced with `FORMAT()`; quarter via `ROUNDUP(MONTH/3)`.
  2. Calculated-table relationship endpoints failed PBIP validation ("invalid column ID") → **DateTable is now a Power Query (M) table**, not a DAX calculated table. Its columns are real storage columns; relationships bind cleanly.
  3. Charts were blank because value-slot columns were bare `Column` refs → now wrapped in `Aggregation` (Average for rate/pct/share/ppt, Sum for counts) in `_visual_container`.

### PENDING (next session, in order)
1. **Confirm charts render + semantic fixes look right.** Reopen `.pbip` (close Desktop WITHOUT saving first) and refresh. Verify: charts draw (aggregation fix), the state trend shows one line per state, the FT/PT area shows Persons only, the FT-share line splits by sex, and the "Employment by Sex" bar shows Male/Female for the latest month only.
3. **Data note:** `mart.v_unemployment_by_state` returns only **6** `region_name` values, not the 8 states/territories in the PRD (ACT/NT appear missing). Check the staging→mart filtering if all 8 are wanted on the State page.

### DONE this session (2026-06-18, "All in build_report.py" — source of truth preserved, MCP validation-only)
- **Two semantic fixes (report-level, in `_make_report()`):**
  - FT/PT area chart now filtered to `sex_label = "Persons"` (was triple-counting Persons+Male+Female).
  - State trend line now split by `region_name` series (was averaging all states into one line).
  - Bonus: FT-share line split by sex; "Employment by Sex" bar now excludes the Persons total and is filtered to `is_latest_month = 1` (it had no latest-month filter, so it summed totals over all history).
  - New report helpers: `_lit`, `_categorical_filter(table, col, values, exclude=)`, and `vfilters=` on `_visual_container`/`_line`/`_bar`/`_area`; `_line` now takes `series_table`/`series_col`.
- **Model polish (in `_make_model()`):** hid `region_code` + `industry_code`; added table descriptions (all 5 data tables + DateTable), key column descriptions, and measure descriptions (subtitles, National Avg, Latest FT/PT Share). `c()` gained `desc=`, `_m_table` gained `description=`, measures tuples accept an optional 5th description element.
- Regenerated via `py -3 powerbi/build_report.py`; `model.bim` + `report.json` validated as well-formed and fixes confirmed present.

### Tooling added this session
