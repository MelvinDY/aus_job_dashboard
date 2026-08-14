# Australian Labour Market Analytics — project spec for Claude Code

## Project Overview

An end-to-end data analytics portfolio project for Melvin Darial Yogiana. It ingests real
Australian Bureau of Statistics (ABS) Labour Force data, lands it in a local SQL Server
warehouse, models it into a star schema with dbt, and delivers it as a Power BI report and
an Excel workbook.

**Goal:** Demonstrate the full analyst stack (ingest → model → visualise) on real government
data, reproducibly and at zero cost, for melvindy.vercel.app/projects/data.

**Governing documents.** `PRD.md` is the requirements spec (v2). This file governs *how the
work is done* — conventions, decisions, status, handoff. `powerbi/build_report.py` governs
the generated `.pbip` files only; it is a build mechanism, not a competing authority. When
they appear to disagree, PRD.md defines the goal, CLAUDE.md wins on execution, and this file
gets updated.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Data source | ABS Data API (`data.api.abs.gov.au/rest`) — no API key |
| Ingestion | Python 3, requests, pandas |
| Warehouse | **SQL Server 2022 Developer edition in Docker** (free, local) |
| Transformation | **dbt (`dbt-sqlserver`)** — staging → star schema → mart |
| Visualisation | Power BI Desktop (`.pbip`, generated) + Excel / Power Query |
| Version control | GitHub |

**Cost: $0.** v1 ran on Azure SQL and that instance was decommissioned on purpose. Do not
re-provision it. A cloud target stays *documented* (the `azure` target in `dbt/profiles.yml`,
the commented block in `.env.example`) and never *required*.

---

## Repository Structure

```
aus_job_dashboard/
├── PRD.md                  # v2 requirements
├── CLAUDE.md               # this file
├── README.md               # public docs
├── docker-compose.yml      # SQL Server Developer + seeded database
├── run_pipeline.py         # one command, end to end
├── data/raw/               # ABS responses (gitignored)
├── scripts/
│   ├── extract.py          # ABS Data API -> data/raw
│   ├── load_raw.py         # data/raw -> schema `raw`, verbatim
│   ├── export_mart.py      # mart -> excel/data/*.csv
│   ├── build_workbook.py   # generates the Excel workbook (needs Excel + pywin32)
│   └── export_dashboard.py # renders dashboard PDF + PNG from the mart
├── dbt/
│   ├── models/staging/     # stg_labour_force + sources
│   ├── models/marts/core/  # dim_date, dim_series, fct_labour_force
│   ├── models/marts/reporting/  # the four mart views
│   ├── seeds/              # ABS code -> label mappings
│   ├── tests/              # singular data-quality tests
│   ├── macros/             # generate_schema_name
│   └── profiles.yml        # local target (default) + documented azure target
├── powerbi/                # build_report.py + generated .pbip
├── excel/                  # workbook + committed mart export + README
└── docs/migration-v1-to-v2.md
```

---

## Pipeline

```
ABS Data API → data/raw/*.csv → raw.* → stg_labour_force → dim_*/fct_* → mart.v_*
                extract.py       load_raw.py  ────────── dbt ──────────
                                                                        ├→ Power BI
                                                                        └→ Excel
```

**Python calls the API and lands the response. That is all it does.** Every transformation
after that is a dbt model with tests and docs attached. Do not add cleaning, reshaping or
derivation to a Python script — it belongs in a model where it can be tested.

Run it: `docker compose up -d && py -3 run_pipeline.py`
(`--skip-extract` to rebuild from disk, `--full-refresh` to rebuild seeds and tables.)

---

## Environment gotchas (read first)

- **Python:** bare `python` is a Windows Store stub that fails. Use **`py -3`**.
- **dbt:** `py -3 -m dbt` does **not** work (dbt is a package with no `__main__`). The
  console script lives in `…\Python313\Scripts\dbt.exe`, which is not on PATH.
  `run_pipeline.py` resolves it from `sys.executable`. Running dbt by hand:
  `cd dbt && DBT_PROFILES_DIR=. …/Scripts/dbt.exe build`
- **dbt profiles:** `profiles.yml` is checked into `dbt/`, not `~/.dbt/`. Set
  `DBT_PROFILES_DIR` or run through `run_pipeline.py`.
- **Docker:** the engine must actually be running, not just installed — start Docker Desktop
  first. `docker compose up -d` seeds the database on every run and is idempotent.
- **Git Bash mangles container paths.** `docker exec … /opt/mssql-tools18/bin/sqlcmd` gets
  rewritten to a Windows path and fails. Prefix with `MSYS_NO_PATHCONV=1`, or connect from
  Python instead.
- **T-SQL reserved words** bite in CTE names: `national` is reserved (`NATIONAL CHARACTER`)
  and produced a syntax error. `national_measures` is fine.

---

## Coding Conventions

- Python: PEP 8, functions over scripts, no hardcoded credentials, each script runnable
  standalone.
- SQL/dbt: lowercase keywords, snake_case, explicit column lists in mart models. Every model
  declares its grain in a header comment **and** enforces it with a uniqueness test.
- Every model and every mart column carries a `description` in the schema YAML.
- dbt generic tests use the 1.12 form: arguments nested under `arguments:`, `config:`
  alongside it. The bare form is deprecated and warns.
- Comments explain *why*, especially where the code encodes a data-quality trap.

---

## Data-quality rules that must not regress

These are encoded as tests. If one fails, the data or the model is wrong — do not weaken
the test.

1. **All eight jurisdictions.** The ABS publishes no seasonally adjusted series for NT or
   ACT; requesting all eight on that basis returns six with HTTP 200 and no warning. v1
   shipped a map missing two territories. `assert_all_jurisdictions_present` catches the gap;
   `extract.py`'s `expect: {"REGION": 8}` catches it earlier still.
2. **One adjustment basis per comparison.** The obvious fix for (1) — back-filling NT/ACT
   with Original estimates — is worse than the bug. The state page uses **Trend**, which
   exists for all eight. `assert_no_mixed_adjustment_types` enforces it. Consequence to keep
   labelled: state figures do not match the seasonally adjusted headline rate in the news.
3. **Persons = Male + Female.** Not a third category. Anything aggregating all three
   double-counts; v1's area chart did.
4. **Industry data is annual and lags by years.** The monthly LF dataflow has no industry
   dimension, so industry comes from `ABS_LABOUR_ACCT` (annual, published late) — confirmed
   against the live API, so re-running `extract.py` will not help. Titles state the vintage.
   Options if it ever needs to be current: a quarterly Labour Force Detailed "employed by
   industry" release (needs a CSV download and a new model — not exposed as a simple Data-API
   dataflow), or leave it labelled. Census 2021 is point-in-time, not a series.

---

## Power BI — SOURCE OF TRUTH

- The `.pbip` is **generated** by `powerbi/build_report.py`. **Do NOT hand-edit
  `model.bim` / `report.json`** — edit `build_report.py` and regenerate:
  `py -3 powerbi/build_report.py`. (Hand-editing plus a Desktop re-save previously corrupted
  the model into a state that would not load.)
- After regenerating, **close Power BI Desktop without saving** before reopening the
  `.pbip`, or Desktop overwrites the generated files.
- The model binds to `localhost,1433` / `aus_job_dashboard` by default; override with
  `PBI_SERVER` / `PBI_DATABASE`. It reads `mart.v_*` and nothing else, so it does not care
  which warehouse built them.
- Power BI keeps its **own daily `DateTable`** (Power Query) rather than importing
  `core.dim_date`. Deliberate: DAX time intelligence needs a contiguous *daily* table, while
  `dim_date` is month grain because that is the ABS publication grain. Do not "fix" this by
  repointing it without checking the measures.

### Hard-won report.json lessons (each cost real debugging time)

1. DateTable DAX used `TEXT()` (Excel, not DAX) → use `FORMAT()`; quarter via `ROUNDUP(MONTH/3)`.
2. Calculated-table relationship endpoints fail PBIP validation ("invalid column ID") →
   DateTable is a **Power Query (M) table**, so its columns are real storage columns.
3. A value-slot column must be wrapped in an **`Aggregation`** (Average for rate/pct/share/ppt,
   Sum for counts) or the visual renders blank.
4. `compatibilityLevel` must be **1600**. Desktop upgraded the workspace and refuses to load a
   lower level. Never lower it.
5. Each page sets `width: 1280, height: 720, displayOption: 1` (Fit to Page), or right-edge
   visuals clip.
6. Per-period fact tables need visual-level filters to collapse to one row per entity:
   industry bar/table → `is_latest_year=1`; industry trend → `is_focus_industry=1`; state
   bars → `is_latest_month=1`.
7. **`vcObjects`, NOT `visualContainerObjects`** — container formatting (title, background,
   border, shadow) under the latter is **silently ignored**, so every custom title fell back
   to an auto name like "employed_thousands by industry_name". In report.json a wrong
   property name fails quietly. This is the single most important lesson here.
8. `labelDisplayUnits`: **0 = Auto** (abbreviated 14,737 → "14.7K"), **1 = None**. Card value
   font 24, not 30 (30 truncated "+0.21 ppt").
9. Units live in format strings: `0.00"%"`, `+0.00" ppt"`. ABS values are already ×100, so
   append a literal `%` rather than using a percent format, which would multiply again.
10. Per-visual field renames = `columnProperties` keyed by queryRef with a `displayName`.
    Sort by value = an `OrderBy` in the visual's prototypeQuery (Direction 2 = descending).
11. Custom theme (`AusLabourTheme.json`) in `StaticResources/RegisteredResources/`, wired via
    `resourcePackages` + `config.themeCollection.customTheme`. Its `dataColors` drives
    categorical palettes theme-wide. No `baseTheme` referenced (avoids a version-specific name).
12. The built-in **map visual was dropped** — it rendered as a zoomed-out world map and read
    as broken. Two ranked bars tell the state story better. Page navigation uses the built-in
    `pageNavigator` visual.

---

## Status (updated 2026-08-14)

**PRD v2 is implemented end to end.** All four phases (P1 local warehouse, P2 dbt project,
P3 rebind + regression, P4 Excel + README) are complete and verified:

- `docker compose up -d && py -3 run_pipeline.py` runs green from a cold start: live ABS
  extract → 20,767 fact rows → **137/137 dbt nodes pass** (5 seeds, 3 tables, 5 views,
  124 tests). Data current to **June 2026**, all 8 jurisdictions.
- Star schema: `dim_date` (581), `dim_series` (137), `fct_labour_force` (20,767).
- **Regression vs v1: every displayed number identical.** Three marts match exactly; the
  fourth differs on 2 of 494 rows by 0.01 because v1 divided an already-rounded numerator —
  v1 was wrong, and neither row is displayed by any visual. Evidence in
  `docs/migration-v1-to-v2.md`.
- Power BI rebound to the local warehouse; all 4 tables verified to bind to the dbt marts
  with matching column lists.
- Excel workbook generated with 3 Power Query sheets + PivotTable + slicer; Refresh All
  verified working on a fresh open.
- Retired (in git history): `sql/`, `transform.py`, `load.py`, `deploy_views.py`,
  `check_views.py`.

### Possible next steps (none blocking)

- Real Power BI Desktop screenshots for the portfolio — `powerbi/dashboard_overview.png` is
  a matplotlib render, not the polished Desktop look. Claude cannot capture these; Melvin
  takes them in Desktop.
- Make the generated GUIDs in `build_report.py` deterministic to cut git diff noise.
- The quarterly industry source (see data-quality rule 4) if the 2022 vintage ever becomes
  unacceptable.

### Tooling

- Skill `powerbi-modeling` at `.claude/skills/powerbi-modeling/`.
- MCP server `powerbi-modeling` (user scope) edits the **live** model and requires Desktop
  open. If used, remember `build_report.py` is authoritative — they will diverge otherwise.
