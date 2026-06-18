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
- The `.pbip` is **generated** by `powerbi/build_report.py`. **Do NOT hand-edit `model.bim` / `report.json`** — edit `build_report.py` and regenerate: `py -3 powerbi/build_report.py`. (Hand-editing + Desktop re-saves previously corrupted the model into a state that wouldn't load.)
- After regenerating, **close Power BI Desktop without saving** before reopening `aus_job_dashboard.pbip`, or Desktop overwrites the regenerated files.
- Fixes already applied in `build_report.py`:
  1. DateTable DAX used `TEXT()` (Excel, not DAX) → replaced with `FORMAT()`; quarter via `ROUNDUP(MONTH/3)`.
  2. Calculated-table relationship endpoints failed PBIP validation ("invalid column ID") → **DateTable is now a Power Query (M) table**, not a DAX calculated table. Its columns are real storage columns; relationships bind cleanly.
  3. Charts were blank because value-slot columns were bare `Column` refs → now wrapped in `Aggregation` (Average for rate/pct/share/ppt, Sum for counts) in `_visual_container`.

### PENDING (next session, in order)
1. **Confirm charts render.** Last user report: model loads + data OK + cards/text OK, but charts were broken; the aggregation fix (#3 above) is **uncommitted and untested by the user**. Ask them to reopen `.pbip` and confirm charts draw.
2. **Two semantic fixes** (render fine but numbers need correcting):
   - Full-time vs Part-time area/line: `FulltimeParttime.sex_label` ∈ {Persons, Male, Female} where Persons = Male+Female; summing all three double-counts. Add a visual filter `sex_label = "Persons"` (or split by sex).
   - State trend line: currently averages all states into one line; split into one line per state via `region_name` series.
3. **Model polish** (from the installed `powerbi-modeling` skill's best practices): hide technical columns (`region_code`, `sex_code`, `industry_code`, `is_latest_*` flags); add table/column/measure descriptions.
4. **Commit + push** once charts are confirmed. Uncommitted now: `powerbi/build_report.py`, `model.bim`, `report.json`, `definition.pbism` (regenerated), and `.claude/skills/powerbi-modeling/` (the installed skill).

### Tooling added this session
- **Skill** `powerbi-modeling` installed at `.claude/skills/powerbi-modeling/` (reference docs for star schema, relationships, DAX, performance, RLS).
- **MCP server** `powerbi-modeling` registered at **user scope** in `~/.claude.json` (stdio: the VS Code extension's `…\analysis-services.powerbi-modeling-mcp-0.4.0-win32-x64\server\powerbi-modeling-mcp.exe --start`). Exposes `connection_operations`, `table_operations`, `measure_operations`, `relationship_operations`, etc. **Only available after a Claude Code restart**, and it edits the **live** model (requires Power BI Desktop open). If used, decide whether the live model or `build_report.py` is authoritative — they will diverge otherwise.
