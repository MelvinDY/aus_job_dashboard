# PRD v2 — Revival on a Free, Reproducible Microsoft Stack

**Owner:** Melvin Darial Yogiana
**Status:** Draft v2 · August 2026
**Current state:** v1 shipped and then archived — Azure SQL was torn down deliberately, so the pipeline no longer runs end-to-end for anyone, including its author
**Stack added:** SQL Server in Docker · dbt (`dbt-sqlserver`) · Excel / Power Query

---

## 1. Background & positioning

v1 was a genuine end-to-end pipeline: ABS Data API → Python extract/transform →
Azure SQL staging and mart views → a four-page Power BI report generated as code.
The Power BI work is the strongest artifact in the portfolio's Microsoft column,
and the finding it produced (80% of working men in full-time work versus 57% of
women) is the most-quoted number on the site.

Then the Azure SQL instance was decommissioned — correctly, because a portfolio
project should not carry a monthly bill. The cost of that decision is that the
repo is now a description of a pipeline rather than a pipeline: clone it, and
step three fails on a missing connection string.

This is also the most **Sydney-shaped** project of the four. Local job ads lean
heavily on the Microsoft ecosystem — Azure, Microsoft Fabric, Power BI — and
Power BI alone appears in roughly 43% of Australian data-analyst ads against
about 2% for Tableau. Separately, **Excel is named in around 81% of data-analyst
job descriptions, more than any other tool**, and appears nowhere in this
portfolio.

v2 therefore has two jobs: **make it run again at zero cost**, and **add the two
things the market asks for that the project is one step away from** — modelled
dimensional SQL under version control, and an Excel deliverable.

## 2. Goals

| # | Goal | Measure of success |
|---|------|--------------------|
| G1 | Runs end-to-end again, free | `docker compose up` + `python run_pipeline.py` takes a stranger from ABS API to built marts with no cloud account and no keys |
| G2 | Transformations are modelled, not scripted | SQL views replaced by dbt models with tests; the star schema is explicit and documented |
| G3 | Dimensional modelling stated in the vocabulary interviewers use | A fact table and named dimensions, with grain declared per model and a diagram in the README |
| G4 | An Excel deliverable | A workbook driven by Power Query off the mart, refreshable in one click, committed with a short usage note |
| G5 | Power BI report survives the migration | The existing four pages rebind to the new mart with no visual regressions and no changed numbers |

## 3. Non-goals

- **No re-provisioning of Azure SQL.** The teardown was deliberate and stays. Any cloud target is a documented option, never a requirement to run the project.
- **No Fabric capacity purchase.** `dbt-sqlserver` against local SQL Server keeps the T-SQL dialect close enough that a Fabric or Azure SQL target is a profile change if it is ever wanted; that path is documented, not built.
- No new ABS series or dashboard pages. v2 is about reproducibility and modelling, not scope.
- No change to the published finding. If the ported models move a number, the number on the portfolio gets corrected — the models do not get bent back to match it.

## 4. Users

| User | Need |
|------|------|
| Hiring manager / recruiter (primary) | See a live-looking project with a Power BI screenshot, an Excel download, and a stack line that reads dbt · SQL Server · Power BI |
| Technical interviewer | Clone and run it; read the star schema; ask why a fact table is at the grain it is |
| Melvin (operator) | One command to a full local rebuild; no bill, no secrets |

## 5. Data & grain

| Layer | Grain | Notes |
|-------|-------|-------|
| `data/raw/` | ABS series response per download | Unchanged; append-only, one file per pull |
| `stg_labour_force` | (series_id, period) | Cleaning and typing ported from `transform.py` |
| `dim_date` | (date_key) | Standard date dimension, month grain |
| `dim_series` | (series_id) | Sex, state, industry, employment type, adjustment type — the attributes currently buried in series metadata |
| `fct_labour_force` | (series_id, period) | The single fact; measures are the ABS values, dimensions join out |

**The gotcha to preserve in a test, not a comment:** the ABS does not publish
seasonally-adjusted series for every state — NT and ACT among them. A state
comparison that silently mixes adjusted and original series is wrong in a way
that looks fine on a chart. `dim_series` carries the adjustment type, and a test
asserts no mart mixes adjustment types within one comparison.

## 6. Functional requirements

### FR-1 Local warehouse (`docker-compose.yml`)
- SQL Server (Developer edition image, free for non-production) with a named volume and a seeded empty database.
- `.env.example` updated: local connection string is the default; the Azure variable stays documented as an alternative target.

### FR-2 dbt project (`dbt/`)
- `dbt-sqlserver` adapter; staging → dimensions → fact, replacing the hand-written views in `sql/`.
- Tests: grain uniqueness on every model, `not_null` on keys, `accepted_values` on sex/state/adjustment type, relationship tests from fact to each dimension, plus the adjustment-type consistency test above.
- Every model and mart column documented; `dbt docs` generated locally (hosting optional).

### FR-3 Pipeline entry point (`run_pipeline.py`)
- One command: extract → load raw → `dbt build` → export Excel refresh source.
- `--skip-extract` to rebuild from existing raw files, matching the convention in the grocery project.

### FR-4 Excel deliverable (`excel/`)
- Workbook connected via Power Query to the mart export: a national trend sheet, a state comparison sheet, and a full-time/part-time by sex sheet carrying the headline finding.
- One PivotTable and one slicer, because that is what the reader who asked for Excel actually wants.
- `excel/README.md`: how to refresh, and what the adjustment-type caveat means for the state sheet.

### FR-5 Power BI rebind
- Repoint the existing semantic model at the dbt-built mart; keep `build_report.py` as the generation path.
- Regression check: every KPI on every page compared against the pre-migration export before the old `sql/` views are deleted.

### FR-6 Documentation
- README rewritten around the local-first flow, with the star-schema diagram, the free-to-run promise, and an honest note that v1 originally ran on Azure SQL and why it no longer does.

## 7. Milestones

| Phase | Deliverable | Estimate |
|-------|-------------|----------|
| P1 | Local SQL Server up; raw load working against it | Half a day |
| P2 | dbt project: staging, dimensions, fact, tests green | 1–2 days |
| P3 | Power BI rebind + regression check against v1 numbers | 1 day |
| P4 | Excel workbook + README rewrite + star-schema diagram | 1 day |

## 8. Risks

| Risk | Mitigation |
|------|------------|
| ABS API shape has drifted since v1 | Extract is the first thing rebuilt; if a series moved, the change is recorded in the README rather than patched silently |
| Ported models change the headline 80/57 figure | Reconcile before deleting the old views; if it moves, the site copy is corrected — the finding follows the data |
| SQL Server container is heavy on a laptop | Document memory settings; DuckDB is *not* substituted here, because the T-SQL dialect is part of what this project is demonstrating |
| Excel workbook rots when the mart schema changes | Power Query steps documented; the mart export is a stable contract, versioned with the models |

## 9. Cost

$0. SQL Server Developer edition in Docker, Power BI Desktop, Excel already
licensed, no cloud resources provisioned.

## 10. Definition of done

A clean clone runs to built marts in one command with no cloud account, the star
schema and its grain are documented, the Power BI pages reproduce v1's numbers
exactly, an Excel workbook refreshes off the mart, and the README no longer
describes infrastructure that does not exist.
