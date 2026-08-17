# Australian Labour Market Analytics — engineering notes

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
they appear to disagree, PRD.md defines the goal, docs/engineering-notes.md wins on execution, and this file
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
├── docs/engineering-notes.md               # this file
├── README.md               # public docs
├── docker-compose.yml      # SQL Server Developer + seeded database
├── run_pipeline.py         # one command, end to end
├── data/raw/               # ABS responses (gitignored)
├── .github/workflows/      # ci.yml (fixture, every push) + abs-freshness.yml (live, weekly)
├── tests/fixtures/raw/     # trimmed real extract so CI never calls the ABS API
├── scripts/
│   ├── extract.py          # ABS Data API -> data/raw
│   ├── load_raw.py         # data/raw -> schema `raw`, verbatim (--raw-dir for the fixture)
│   ├── init_warehouse.py   # wait for the server, seed the database (used by CI)
│   ├── make_fixture.py     # data/raw -> tests/fixtures/raw
│   ├── check_mart_contract.py  # guards the mart -> Power BI / Excel seam
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

## HANDOFF — next session starts here (updated 2026-08-17)

### Where the project stands

**PRD v2 is implemented, verified, committed, merged and pushed**, and CI now runs on top
of it (next step 3 below, done 2026-08-17). Nothing is in flight. All four PRD phases:

- `docker compose up -d && py -3 run_pipeline.py` runs green **from a destroyed volume**:
  live ABS extract → 21,560 raw rows → **137/137 dbt nodes pass** (5 seeds, 3 tables,
  5 views, 124 tests) → Excel export. Verified this way, not assumed.
- Data current to **June 2026**, all 8 jurisdictions present.
- Star schema: `dim_date` (581), `dim_series` (137), `fct_labour_force` (20,767).
- **Regression vs v1: every displayed number is identical.** Three marts match cell for
  cell; the fourth differs on 2 of 494 rows by 0.01 because v1 divided an already-rounded
  numerator. v1 was wrong, and neither row is displayed by any visual. Full evidence in
  `docs/migration-v1-to-v2.md`.
- Excel workbook: 3 Power Query sheets + PivotTable + slicer, Refresh All verified on a
  fresh open after a full warehouse rebuild.
- Retired into git history: `sql/`, `transform.py`, `load.py`, `deploy_views.py`,
  `check_views.py`.

### The one thing NOT verified

**Nobody has opened the Power BI report since the rebind.** It needs a GUI, so this is
the single open item. What *was* verified programmatically: all 4 model tables bind to the
dbt marts with matching column lists, `model.bim`/`report.json` are valid JSON,
compatibilityLevel is 1600, and the report still has 4 pages / 15 measures / 4 relationships.

This one has to be done by hand:
1. Open `powerbi/aus_job_dashboard.pbip` → **Home > Refresh All**.
2. Auth prompt → **Database** auth, user `sa`, password `LocalDev_Passw0rd!`.
3. If it complains about encryption, trust the container's self-signed certificate.
4. Re-mark `DateTable` as the date table if Desktop lost it (right-click → Mark as date table → `Date`).

If a visual is blank or a title reads like `employed_thousands by industry_name`, do NOT
fix it in Desktop — that is a `build_report.py` bug. See report.json lessons 3 and 7 above.

### Next steps, in the order I would do them

1. **Real Power BI Desktop screenshots** (blocked on the refresh above).
   `powerbi/dashboard_overview.png` is a matplotlib render standing in as the README hero
   image since v1. Capture all four pages full-canvas → `powerbi/screenshots/`
   (`pbi_overview.png`, `pbi_state.png`, `pbi_industry.png`, `pbi_ftpt.png`) and swap the
   README image. Overview and State are the strongest hero shots. **This cannot be automated.**
2. **Update the portfolio page** at melvindy.vercel.app/projects/data. It still describes
   Azure SQL, which no longer exists. New stack line: `Python · dbt · SQL Server · Power BI
   · Excel`. Numbers moved — data is current to June 2026 and the headline finding is now
   **80.0% of employed men full-time vs 56.6% of women** (was ~80/57, so the story holds).
   Source material: `README.md` and `docs/migration-v1-to-v2.md`. Note `PROJECT_NOTES.txt`
   section 9's KEY NUMBERS are the April/May vintage — re-read from the mart before quoting.
3. ~~CI on GitHub Actions~~ — **DONE 2026-08-17.** Two workflows, split by what a failure
   means. `ci.yml` runs on every push/PR from the committed fixture (no ABS call, so a red
   badge always means someone broke a model); `abs-freshness.yml` runs the live extract
   weekly as a drift canary. Both stand up an mssql service container. Verified locally by
   building the whole thing from the fixture in a throwaway database: 137/137 pass.
   **Not yet observed running on GitHub** — the first push will be its real test. If the
   driver install step fails, that is the suspect (it tracks `lsb_release -rs`, so a runner
   image change is the likely cause).
4. Smaller, whenever they become annoying: deterministic GUIDs in `build_report.py` to cut
   git diff noise; publish `dbt docs` to GitHub Pages; the quarterly industry source (see
   data-quality rule 4) if the 2022 vintage ever becomes a sticking point.

### About the CI fixture

`tests/fixtures/raw/` is a **date-trimmed copy of a real extract** (2015 onward for the
monthly files; the annual industry file kept whole), 576 KB, regenerated with
`py -3 scripts/make_fixture.py`. It is not synthetic, and the trim is constrained: it must
keep all 8 jurisdictions in every month, both sides of the deliberately overlapping series,
and ≥13 months so the 12-month lags resolve. `make_fixture.py` asserts the jurisdiction
count rather than trusting the trim.

It does **not** need regenerating on a schedule — it exists to be stable. Regenerate it only
when a *model* needs input the fixture does not contain (a new measure, dataflow or
dimension). CI passing on a fixture from 2026 while the live pipeline has moved on is fine
and intended; `abs-freshness.yml` is what watches the live data.

`scripts/check_mart_contract.py` runs at the end of CI and is worth knowing about: it
compares the columns `model.bim` declares, and the committed Excel export headers, against
what the mart views actually return. It exists because Power Query binds by **name**, so a
renamed mart column leaves dbt green and breaks both deliverables silently. It was
negative-tested (rename a column → exit 1), not just assumed to work.

### Environment state as of session end

- Docker container `aus_job_warehouse` was left **running and healthy**. Tomorrow it may be
  stopped (Docker Desktop restart) — `docker compose up -d` brings it back with data intact.
  The named volume `aus_job_dashboard_mssql_data` persists across `down`, and only
  `down -v` destroys it.
- **Docker Desktop must actually be started** before any `docker` command works — installed
  is not the same as running. This cost time at the start of the last session.
- `PROJECT_NOTES.txt` is **deliberately untracked**. It carries Azure billing figures and
  portfolio-positioning notes that do not belong in a public repo a recruiter reads. It has
  a v2 status banner prepended so it cannot mislead. Do not `git add` it without asking.
- `origin/feat/v2-local-dbt-stack` still exists and is fully merged; safe to delete.
- The `aus_job_dashboard_v1` regression database no longer exists — the volume was destroyed
  during the clean-rebuild test. To re-run that comparison you would need to restore the
  v1 `sql/` views and `transform.py`/`load.py` from git history (commit `90e8e15`).

### Standing rules — do not undo these

- **No tool attribution in commit messages.** Commits end on the last line of the body.
  Melvin stated this explicitly; these are public portfolio repos under his own name.
- **Do not re-provision Azure SQL.** The teardown was deliberate (PRD non-goal 1). A cloud
  target stays documented and never required.
- **Do not hand-edit `model.bim` / `report.json`.** Edit `build_report.py` and regenerate.
- **Do not weaken a failing dbt test.** The two jurisdiction/adjustment tests encode bugs
  that actually shipped; a failure means the data or the model is wrong.
- **Do not move transformation logic back into Python.** Python calls the API and lands the
  response; everything else is a dbt model.

  open. If used, remember `build_report.py` is authoritative — they will diverge otherwise.

  open. If used, remember `build_report.py` is authoritative — they will diverge otherwise.
