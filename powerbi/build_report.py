"""
build_report.py — Generate aus_job_dashboard.pbip (Power BI Project format).

The .pbip format is Power BI's text-based, version-controlled project format.
Open the generated file in Power BI Desktop (Nov 2022 or later).

OUTPUT FILES:
  powerbi/aus_job_dashboard.pbip
  powerbi/aus_job_dashboard.SemanticModel/definition.pbism
  powerbi/aus_job_dashboard.SemanticModel/model.bim
  powerbi/aus_job_dashboard.Report/definition.pbir
  powerbi/aus_job_dashboard.Report/report.json

BEFORE RUNNING:
  1. Build the warehouse: docker compose up -d && py -3 run_pipeline.py
  2. Run: py -3 powerbi/build_report.py
  3. Open powerbi/aus_job_dashboard.pbip in Power BI Desktop, then Refresh

The model reads the dbt-built views in the `mart` schema and nothing else, so
the report does not care whether that schema was produced by the local
container, Azure SQL or Fabric — only where to find it.
"""

import json
import os
import uuid
from pathlib import Path

# ── Warehouse the report binds to ────────────────────────────────────────────
# Defaults to the local SQL Server container, so a clean clone opens the report
# against a warehouse it can actually build. v1 pointed at Azure SQL; that
# instance was decommissioned deliberately, and the environment variables below
# are how you point this at a cloud warehouse instead without editing the file.
SERVER   = os.getenv("PBI_SERVER",   "localhost,1433")
DATABASE = os.getenv("PBI_DATABASE", "aus_job_dashboard")
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).resolve().parent
MODEL_DIR  = BASE_DIR / "aus_job_dashboard.SemanticModel"
REPORT_DIR = BASE_DIR / "aus_job_dashboard.Report"


def jdump(obj) -> str:
    """Serialize a Python object to a compact JSON string (for embedding in other JSON)."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def write_json(path: Path, data, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote: {path.relative_to(BASE_DIR)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC MODEL (model.bim)
# ═══════════════════════════════════════════════════════════════════════════════

def _col(name, dtype, source=None, fmt=None, hidden=False):
    c = {"name": name, "dataType": dtype, "sourceColumn": source or name}
    if fmt:
        c["formatString"] = fmt
    if hidden:
        c["isHidden"] = True
    c["annotations"] = [{"name": "SummarizationSetBy", "value": "Automatic"}]
    return c


def _m_table(name: str, sql: str, columns: list, description: str = None) -> dict:
    """Build a table definition backed by an Azure SQL M query."""
    transforms = ", ".join(
        "{" + f'"{c["name"]}", {c["mtype"]}' + "}"
        for c in columns
    )
    expression = [
        "let",
        f'    Source = Sql.Database("{SERVER}", "{DATABASE}",'
        f' [Query = "{sql}"]),',
        f'    #"T" = Table.TransformColumnTypes(Source, {{{transforms}}})',
        "in",
        '    #"T"',
    ]
    cols = []
    for c in columns:
        col = {
            "name": c["name"],
            "dataType": c["dataType"],
            "sourceColumn": c["name"],
            "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}],
        }
        if c.get("fmt"):
            col["formatString"] = c["fmt"]
        if c.get("hidden"):
            col["isHidden"] = True
        if c.get("desc"):
            col["description"] = c["desc"]
        if c.get("dcat"):
            col["dataCategory"] = c["dcat"]
        cols.append(col)
    table = {
        "name": name,
        "columns": cols,
        "partitions": [{
            "name": "Partition",
            "mode": "import",
            "source": {"type": "m", "expression": expression},
        }],
    }
    if description:
        table["description"] = description
    return table


def _make_model() -> dict:
    # ── Column specs ──────────────────────────────────────────────────────────
    def c(name, dtype, mtype, fmt=None, hidden=False, desc=None, dcat=None):
        return {"name": name, "dataType": dtype, "mtype": mtype,
                "fmt": fmt, "hidden": hidden, "desc": desc, "dcat": dcat}

    national_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("employed_thousands",            "double",   "type number", "#,0.0"),
        c("unemployed_thousands",          "double",   "type number", "#,0.0"),
        c("unemployment_rate_pct",         "double",   "type number", '0.00"%"'),
        c("participation_rate_pct",        "double",   "type number", '0.00"%"'),
        c("emp_to_pop_ratio_pct",          "double",   "type number", '0.00"%"'),
        c("unemployment_rate_mom_change_ppt", "double","type number", '+0.00" ppt";-0.00" ppt"'),
        c("employed_mom_change_pct",       "double",   "type number", '+0.00"%";-0.00"%"'),
        c("unemployment_rate_yoy_change_ppt","double", "type number", '+0.00" ppt";-0.00" ppt"'),
        c("employed_yoy_change_pct",       "double",   "type number", '+0.00"%";-0.00"%"'),
        c("is_latest_month",               "int64",    "Int64.Type",  hidden=True),
    ]
    state_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("region_code",                   "string",   "type text",   hidden=True),
        c("region_name",                   "string",   "type text",
          desc="State or territory name.", dcat="StateOrProvince"),
        c("employed_thousands",            "double",   "type number", "#,0.0",
          desc="Employed persons in thousands, seasonally adjusted."),
        c("unemployment_rate_pct",         "double",   "type number", '0.00"%"',
          desc="Unemployment rate (%), seasonally adjusted."),
        c("unemployment_rate_mom_change_ppt","double", "type number", '+0.00" ppt";-0.00" ppt"'),
        c("unemployment_rate_yoy_change_ppt","double", "type number", '+0.00" ppt";-0.00" ppt"'),
        c("employed_yoy_change_pct",       "double",   "type number", '+0.00"%";-0.00"%"'),
        c("is_latest_month",               "int64",    "Int64.Type",  hidden=True),
    ]
    industry_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("industry_code",                 "string",   "type text",   hidden=True),
        c("industry_name",                 "string",   "type text",
          desc="ANZSIC industry division name."),
        c("employed_thousands",            "double",   "type number", "#,0.0",
          desc="Employed persons in thousands."),
        c("employed_yoy_change_thousands", "double",   "type number", "#,0.0"),
        c("employed_yoy_change_pct",       "double",   "type number", '+0.00"%";-0.00"%"',
          desc="Year-on-year change in employed persons (%)."),
        c("rank_by_employment",            "int64",    "Int64.Type"),
        c("growth_category",               "string",   "type text",
          desc="Growing / shrinking classification based on YoY change."),
        # Declared in the order mart.v_industry_breakdown emits them. Power Query
        # binds these by name, not position, so the order is cosmetic — but a
        # column list that silently disagrees with its source is the kind of
        # thing that makes the next mismatch hard to see.
        c("is_latest_year",                "int64",    "Int64.Type",  hidden=True),
        c("is_focus_industry",             "int64",    "Int64.Type",  hidden=True),
    ]
    ftpt_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("sex_code",                      "string",   "type text",   hidden=True),
        c("sex_label",                     "string",   "type text",
          desc="Persons, Male or Female. Persons = Male + Female, so filter to one "
               "to avoid double-counting in totals."),
        c("employed_fulltime_thousands",   "double",   "type number", "#,0.0"),
        c("employed_parttime_thousands",   "double",   "type number", "#,0.0"),
        c("employed_total_thousands",      "double",   "type number", "#,0.0"),
        c("fulltime_share_pct",            "double",   "type number", '0.00"%"'),
        c("parttime_share_pct",            "double",   "type number", '0.00"%"'),
        c("fulltime_share_yoy_change_ppt", "double",   "type number", '+0.00" ppt";-0.00" ppt"'),
        c("employed_total_yoy_change_pct", "double",   "type number", '+0.00"%";-0.00"%"'),
        c("is_latest_month",               "int64",    "Int64.Type",  hidden=True),
    ]

    # ── DateTable (Power Query / M) ───────────────────────────────────────────
    # Built as an M table rather than a DAX calculated table: relationships that
    # target a calculated-table column fail PBIP validation ("invalid column ID"),
    # whereas M-table columns are real storage columns that bind cleanly — the
    # same pattern the fact tables use.
    date_table = {
        "name": "DateTable",
        "description": "Contiguous daily date dimension (1978→today) for time "
                       "intelligence; marked as the model date table.",
        "columns": [
            {"name": "Date",             "dataType": "dateTime", "isKey": True,
             "formatString": "Short Date",
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
            {"name": "year",             "dataType": "int64",  "formatString": "0",
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
            {"name": "month_number",     "dataType": "int64",  "isHidden": True,
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
            {"name": "month_name",       "dataType": "string",
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
            {"name": "month_year",       "dataType": "string",
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
            {"name": "quarter",          "dataType": "string",
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
            {"name": "financial_year",   "dataType": "string",
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
            {"name": "is_first_of_month","dataType": "int64",  "isHidden": True,
             "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]},
        ],
        "partitions": [{
            "name": "DateTable",
            "mode": "import",
            "source": {
                "type": "m",
                "expression": [
                    "let",
                    "    Start = #date(1978, 1, 1),",
                    "    End = Date.From(DateTime.LocalNow()),",
                    "    Dates = List.Dates(Start, Duration.Days(End - Start) + 1, #duration(1, 0, 0, 0)),",
                    '    Source = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),',
                    '    Typed = Table.TransformColumnTypes(Source, {{"Date", type date}}),',
                    '    A1 = Table.AddColumn(Typed, "year", each Date.Year([Date]), Int64.Type),',
                    '    A2 = Table.AddColumn(A1, "month_number", each Date.Month([Date]), Int64.Type),',
                    '    A3 = Table.AddColumn(A2, "month_name", each Date.ToText([Date], [Format="MMM", Culture="en-AU"]), type text),',
                    '    A4 = Table.AddColumn(A3, "month_year", each Date.ToText([Date], [Format="MMM yyyy", Culture="en-AU"]), type text),',
                    '    A5 = Table.AddColumn(A4, "quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),',
                    '    A6 = Table.AddColumn(A5, "financial_year", each if Date.Month([Date]) >= 7 then "FY" & Text.From(Date.Year([Date]) + 1) else "FY" & Text.From(Date.Year([Date])), type text),',
                    '    A7 = Table.AddColumn(A6, "is_first_of_month", each if Date.Day([Date]) = 1 then 1 else 0, Int64.Type)',
                    "in",
                    "    A7",
                ],
            },
        }],
        "annotations": [
            {
                "name": "__PBI_SemanticLinks",
                "value": jdump([{
                    "LinkTarget": {"TableName": "DateTable", "ColumnName": "Date"},
                    "LinkType": "GlobalCalendar",
                }]),
            }
        ],
    }

    # M-table columns map to a query column via sourceColumn (no calc-column type).
    for _col in date_table["columns"]:
        _col["sourceColumn"] = _col["name"]

    # ── DAX measures ──────────────────────────────────────────────────────────
    measures = [
        # Overview KPIs
        ("Latest Unemployment Rate",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[unemployment_rate_pct]),NationalOverview[date]=D)',
         '0.00"%"', "Overview KPIs"),
        ("Latest Employed Thousands",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[employed_thousands]),NationalOverview[date]=D)',
         "#,0.0", "Overview KPIs"),
        ("Latest Participation Rate",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[participation_rate_pct]),NationalOverview[date]=D)',
         '0.00"%"', "Overview KPIs"),
        ("Latest Emp To Pop Ratio",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[emp_to_pop_ratio_pct]),NationalOverview[date]=D)',
         '0.00"%"', "Overview KPIs"),
        ("Unemployment Rate MoM Change",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[unemployment_rate_mom_change_ppt]),NationalOverview[date]=D)',
         '+0.00" ppt";-0.00" ppt"', "Overview KPIs"),
        ("Employed YoY Change Pct",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[employed_yoy_change_pct]),NationalOverview[date]=D)',
         '+0.00"%";-0.00"%"', "Overview KPIs"),
        ("Unemployment Rate Subtitle",
         'VAR Ch=[Unemployment Rate MoM Change] VAR Ar=IF(Ch>0,"▲",IF(Ch<0,"▼","–")) RETURN Ar&" "&FORMAT(ABS(Ch),"0.0")&" ppt vs last month"',
         None, "Overview KPIs",
         "Arrow + month-on-month change in percentage points, for the KPI card subtitle."),
        ("Employed Subtitle",
         'VAR Ch=[Employed YoY Change Pct] VAR Ar=IF(Ch>0,"▲",IF(Ch<0,"▼","–")) RETURN Ar&" "&FORMAT(ABS(Ch),"0.0")&"% vs last year"',
         None, "Overview KPIs",
         "Arrow + year-on-year employment change (%), for the KPI card subtitle."),
        # State KPIs
        ("National Avg Unemployment Rate",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[unemployment_rate_pct]),NationalOverview[date]=D)',
         '0.00"%"', "State KPIs",
         "National unemployment rate at the latest month (reference line for the state view)."),
        # Industry KPIs
        ("Latest Industry Employed",
         'CALCULATE(MAX(IndustryBreakdown[employed_thousands]),IndustryBreakdown[is_latest_year]=1)',
         "#,0.0", "Industry KPIs"),
        ("Latest Industry YoY Change",
         'CALCULATE(MAX(IndustryBreakdown[employed_yoy_change_pct]),IndustryBreakdown[is_latest_year]=1)',
         '+0.00"%";-0.00"%"', "Industry KPIs"),
        # FT/PT KPIs
        ('Latest FT Share Persons',
         'CALCULATE(MAX(FulltimeParttime[fulltime_share_pct]),FulltimeParttime[is_latest_month]=1,FulltimeParttime[sex_label]="Persons")',
         '0.00"%"', "FT PT KPIs",
         "Full-time share of employment (%) for Persons at the latest month."),
        ('Latest PT Share Persons',
         'CALCULATE(MAX(FulltimeParttime[parttime_share_pct]),FulltimeParttime[is_latest_month]=1,FulltimeParttime[sex_label]="Persons")',
         '0.00"%"', "FT PT KPIs",
         "Part-time share of employment (%) for Persons at the latest month."),
        ('FT Share YoY Change',
         'VAR D=MAX(FulltimeParttime[date]) RETURN CALCULATE(MAX(FulltimeParttime[fulltime_share_yoy_change_ppt]),FulltimeParttime[date]=D,FulltimeParttime[sex_label]="Persons")',
         '+0.00" ppt";-0.00" ppt"', "FT PT KPIs"),
        ('FT Share Subtitle',
         'VAR Ch=[FT Share YoY Change] VAR Ar=IF(Ch>0,"▲",IF(Ch<0,"▼","–")) RETURN Ar&" "&FORMAT(ABS(Ch),"0.0")&" ppt vs last year"',
         None, "FT PT KPIs"),
    ]

    measure_defs = []
    for row in measures:
        name, expr, fmt, folder = row[0], row[1], row[2], row[3]
        desc = row[4] if len(row) > 4 else None
        m = {"name": name, "expression": expr, "displayFolder": folder}
        if fmt:
            m["formatString"] = fmt
        if desc:
            m["description"] = desc
        measure_defs.append(m)

    # Empty partition for _Measures table
    empty_m = [
        "let",
        '    Source = Table.FromRows({}, type table [Placeholder = Int64.Type])',
        "in",
        "    Source",
    ]
    measures_table = {
        "name": "_Measures",
        "isHidden": True,
        # sourceColumn is required even on this throwaway placeholder. Without it
        # the column has no binding to its M query, and while a per-table refresh
        # still works, a FULL MODEL refresh — which is what Desktop's "Refresh
        # All" does — fails the whole batch with:
        #   Column 'Placeholder' in table '_Measures' does not have its source
        #   pipeline rowset column specified.
        # The visible symptom is tables that stay empty with no useful error.
        "columns": [{"name": "Placeholder", "dataType": "int64", "isHidden": True,
                     "sourceColumn": "Placeholder",
                     "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]}],
        "measures": measure_defs,
        "partitions": [{"name": "_Measures", "mode": "import",
                        "source": {"type": "m", "expression": empty_m}}],
    }

    # ── Relationships ─────────────────────────────────────────────────────────
    fact_tables = ["NationalOverview", "UnemploymentByState", "FulltimeParttime", "IndustryBreakdown"]
    relationships = [
        {
            "name": str(uuid.uuid4()),
            "fromTable": tbl,
            "fromColumn": "date",
            "toTable": "DateTable",
            "toColumn": "Date",
            "crossFilteringBehavior": "oneDirection",
        }
        for tbl in fact_tables
    ]

    return {
        "name": "SemanticModel",
        "compatibilityLevel": 1600,
        "model": {
            "culture": "en-AU",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "tables": [
                date_table,
                _m_table("NationalOverview",
                         "SELECT * FROM mart.v_national_overview ORDER BY date",
                         national_cols,
                         description="National monthly labour-force headline series "
                                     "(seasonally adjusted): employment, unemployment "
                                     "rate, participation rate and MoM/YoY changes."),
                _m_table("UnemploymentByState",
                         "SELECT * FROM mart.v_unemployment_by_state ORDER BY region_name, date",
                         state_cols,
                         description="Monthly unemployment rate and employment by "
                                     "state/territory."),
                _m_table("IndustryBreakdown",
                         "SELECT * FROM mart.v_industry_breakdown ORDER BY industry_name, date",
                         industry_cols,
                         description="Employed persons by ANZSIC industry division with "
                                     "year-on-year growth and growing/shrinking category."),
                _m_table("FulltimeParttime",
                         "SELECT * FROM mart.v_fulltime_parttime ORDER BY sex_label, date",
                         ftpt_cols,
                         description="Full-time vs part-time employment split by sex "
                                     "(Persons = Male + Female)."),
                measures_table,
            ],
            "relationships": relationships,
            "annotations": [
                {
                    "name": "PBI_QueryOrder",
                    "value": jdump(["DateTable", "NationalOverview", "UnemploymentByState",
                                    "IndustryBreakdown", "FulltimeParttime", "_Measures"]),
                }
            ],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT (report.json)
# ═══════════════════════════════════════════════════════════════════════════════

_z = 0

def _next_z() -> int:
    global _z
    _z += 1000
    return _z


def _lit(v) -> str:
    """A DAX literal as embedded in a report filter expression — integers become
    long literals (e.g. 1L), everything else a quoted string."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return f"{v}L"
    return "'" + str(v).replace("'", "''") + "'"


def _categorical_filter(table: str, col: str, values: list, *, exclude: bool = False) -> dict:
    """Visual-level categorical filter: keep (or exclude) rows where col ∈ values."""
    alias = "f"
    column_ref = {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": col}}
    in_cond = {"In": {"Expressions": [column_ref],
                      "Values": [[{"Literal": {"Value": _lit(v)}}] for v in values]}}
    condition = {"Not": {"Expression": in_cond}} if exclude else in_cond
    return {
        "name": str(uuid.uuid4()),
        "expression": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": condition}],
        },
        "type": "Categorical",
    }


# ── Visual styling ────────────────────────────────────────────────────────────
# Formatting is applied per-visual via report.json: `objects` (data-level — axes,
# legend, labels, colours) and `visualContainerObjects` (container chrome — title,
# background, border, shadow). Defined once here so every page stays consistent.
PRIMARY    = "#1F4E79"   # hero/accent (deep blue) — unemployment is the lead metric
SECONDARY  = "#E1812C"   # secondary series (amber) — high contrast vs the blue
# Distinct categorical palette for multi-category visuals (donut, split lines).
CATEGORICAL = ["#1F4E79", "#E1812C", "#3F9C5B", "#B23A48", "#6A4C93",
               "#2BB0C5", "#C9A227", "#7A8B99"]

# Category value lists, used to assign a distinct palette colour per series.
STATES = ["New South Wales", "Victoria", "Queensland", "Western Australia",
          "South Australia", "Tasmania"]
FOCUS_INDUSTRIES = ["Construction", "Health Care & Social Assistance",
                    "Information Media & Telecommunications", "Retail Trade"]
SEXES = ["Persons", "Male", "Female"]

THEME_NAME = "AusLabourTheme"   # custom report theme — drives the categorical palette


def _theme_dict() -> dict:
    """Power BI report theme. `dataColors` sets the default categorical palette so
    every multi-series visual (donut, split lines) draws distinct, on-brand colours
    without relying on per-visual selectors."""
    return {
        "name": THEME_NAME,
        "dataColors": CATEGORICAL,
        "foreground": TEXT,
        "foregroundNeutralSecondary": MUTED,
        "background": CARD_BG,
        "tableAccent": PRIMARY,
        "good": "#3F9C5B",
        "bad": "#B23A48",
        "neutral": MUTED,
    }
TEXT       = "#1F2D3D"   # primary text
MUTED      = "#5B6B7B"   # axis / secondary text
CARD_BG    = "#FFFFFF"   # visual background
BORDER     = "#E3E8EF"   # visual border
GRID       = "#ECEFF4"   # gridlines
SHADOW     = "#C7CED8"   # soft drop shadow
PAGE_BG    = "#EEF2F7"   # page canvas
FONT       = "Segoe UI"
FONT_SEMI  = "Segoe UI Semibold"
TITLE_SIZE = 12
CARD_VALUE = 24   # value font; 30 truncated longer values like "+0.21 ppt"


def _pe(value: str) -> dict:
    """Property expression wrapping a DAX literal (e.g. \"true\", \"12D\", \"'Top'\")."""
    return {"expr": {"Literal": {"Value": value}}}


def _color(hex_str: str) -> dict:
    return {"solid": {"color": _pe(f"'{hex_str}'")}}


def _bool(b: bool) -> dict:
    return _pe("true" if b else "false")


def _agg_ref(table: str, field: str) -> str:
    """The queryRef a Y/Size-slot column gets in _visual_container (Average vs Sum)."""
    avg = any(k in field for k in ("rate", "pct", "ratio", "share", "ppt"))
    return f"{'Average' if avg else 'Sum'}({table}.{field})"


def _container_chrome(title: str = None) -> dict:
    vco = {
        "background": [{"properties": {"show": _bool(True), "color": _color(CARD_BG),
                                       "transparency": _pe("0D")}}],
        "border": [{"properties": {"show": _bool(True), "color": _color(BORDER),
                                   "radius": _pe("8D")}}],
        "dropShadow": [{"properties": {"show": _bool(True), "color": _color(SHADOW),
                                       "position": _pe("'Outer'"), "preset": _pe("'BottomRight'")}}],
    }
    if title:
        vco["title"] = [{"properties": {
            "show": _bool(True),
            "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
            "fontColor": _color(TEXT),
            "fontSize": _pe(f"{TITLE_SIZE}D"),
            "fontFamily": _pe(f"'{FONT_SEMI}'"),
            "alignment": _pe("'left'"),
            "titleWrap": _bool(False),
        }}]
    return vco


def _cat_dp(table: str, col: str, values: list) -> list:
    """dataPoint colour selectors keyed by category value (e.g. one colour per
    state / industry / sex), assigned from the categorical palette in order."""
    out = []
    for i, v in enumerate(values):
        out.append({
            "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0,
                "Left": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
                "Right": {"Literal": {"Value": _lit(v)}}}}}]},
            "properties": {"fill": _color(CATEGORICAL[i % len(CATEGORICAL)])},
        })
    return out


def _chart_objects(accent=None, legend=False, data_labels=False,
                   x_axis_title=False, y_axis_title=False, series_colors=None,
                   cat_dp=None) -> dict:
    o = {
        "categoryAxis": [{"properties": {"show": _bool(True), "showAxisTitle": _bool(x_axis_title),
                                         "labelColor": _color(MUTED), "fontSize": _pe("9D")}}],
        "valueAxis": [{"properties": {"show": _bool(True), "showAxisTitle": _bool(y_axis_title),
                                      "labelColor": _color(MUTED), "fontSize": _pe("9D"),
                                      "gridlineColor": _color(GRID)}}],
        "legend": [{"properties": {"show": _bool(legend), "position": _pe("'Top'"),
                                   "showTitle": _bool(False), "labelColor": _color(MUTED),
                                   "fontSize": _pe("9D")}}],
        "labels": [{"properties": {"show": _bool(data_labels), "color": _color(TEXT),
                                   "fontSize": _pe("9D"), "labelDisplayUnits": _pe("0D")}}],
    }
    dp = []
    if accent:
        dp.append({"properties": {"defaultColor": _color(accent), "fill": _color(accent)}})
    for ref, hex_str in (series_colors or []):
        dp.append({"selector": {"metadata": ref}, "properties": {"fill": _color(hex_str)}})
    dp.extend(cat_dp or [])
    if dp:
        o["dataPoint"] = dp
    return o


def _card_objects() -> dict:
    return {
        # labelDisplayUnits 1 = None (0 is Auto, which abbreviated 14,737 to "14.7K").
        "labels": [{"properties": {"color": _color(PRIMARY), "fontSize": _pe(f"{CARD_VALUE}D"),
                                   "fontFamily": _pe(f"'{FONT_SEMI}'"), "labelDisplayUnits": _pe("1D")}}],
        "categoryLabels": [{"properties": {"show": _bool(False)}}],
    }


def _map_objects(accent=PRIMARY) -> dict:
    return {"dataPoint": [{"properties": {"defaultColor": _color(accent), "fill": _color(accent)}}]}


def _table_objects() -> dict:
    return {
        "grid": [{"properties": {"gridVertical": _bool(True), "gridVerticalColor": _color(GRID),
                                 "gridHorizontal": _bool(True), "gridHorizontalColor": _color(GRID),
                                 "outlineColor": _color(GRID), "rowPadding": _pe("3D")}}],
        "columnHeaders": [{"properties": {"fontColor": _color("#FFFFFF"), "backColor": _color(PRIMARY),
                                          "fontFamily": _pe(f"'{FONT_SEMI}'"), "fontSize": _pe("10D")}}],
        "values": [{"properties": {"fontColor": _color(TEXT), "fontSize": _pe("9D"),
                                   "fontFamily": _pe(f"'{FONT}'")}}],
    }


def _visual_container(x, y, w, h, visual_type, projections, title=None,
                       objects=None, extra_config=None, vfilters=None, sort=None,
                       renames=None):
    """
    Build a report visual container dict.
    projections: list of (slot, table, column_or_measure, is_measure)
    sort: optional (slot, "asc"|"desc") — order the query by that slot's value.
    renames: optional {queryRef: friendly name} — per-visual field display names
             (fixes raw column names leaking into legends / table headers).
    """
    vis_name = str(uuid.uuid4())[:8]
    z = _next_z()

    from_map = {}
    from_list = []
    select_list = []
    proj_map = {}
    slot_value_expr = {}   # slot -> value expression (for OrderBy)

    # Slots that aggregate a numeric value. A bare column here produces an
    # invalid visual query, so columns in these slots are wrapped in an
    # Aggregation (Average for rates/shares, Sum for counts).
    agg_slots = {"Y", "Size"}

    for slot, table, field, is_measure in projections:
        alias = table[0].lower() + str(len(from_map))
        if table not in from_map:
            from_map[table] = alias
            from_list.append({"Name": alias, "Entity": table, "Type": 0})
        else:
            alias = from_map[table]

        src_ref = {"SourceRef": {"Source": alias}}

        if is_measure:
            query_ref = f"{table}.[{field}]"
            sel = {"Measure": {"Expression": src_ref, "Property": field}, "Name": query_ref}
        elif slot in agg_slots:
            avg = any(k in field for k in ("rate", "pct", "ratio", "share", "ppt"))
            func = 1 if avg else 0          # 1 = Average, 0 = Sum
            fname = "Average" if avg else "Sum"
            query_ref = f"{fname}({table}.{field})"
            sel = {"Aggregation": {"Expression": {"Column": {"Expression": src_ref,
                                                             "Property": field}},
                                   "Function": func},
                   "Name": query_ref}
        else:
            query_ref = f"{table}.{field}"
            sel = {"Column": {"Expression": src_ref, "Property": field}, "Name": query_ref}
        select_list.append(sel)
        slot_value_expr.setdefault(slot, {k: v for k, v in sel.items() if k != "Name"})

        proj_entry = {"queryRef": query_ref, "active": True}
        if slot not in proj_map:
            proj_map[slot] = []
        proj_map[slot].append(proj_entry)

    proto_query = {
        "Version": 2,
        "From": from_list,
        "Select": select_list,
    }
    if sort and sort[0] in slot_value_expr:
        direction = 2 if sort[1] == "desc" else 1   # 2 = Descending, 1 = Ascending
        proto_query["OrderBy"] = [{"Direction": direction,
                                   "Expression": slot_value_expr[sort[0]]}]

    single_visual = {
        "visualType": visual_type,
        "projections": proj_map,
        "prototypeQuery": proto_query,
    }

    single_visual["vcObjects"] = _container_chrome(title)
    if objects:
        single_visual["objects"] = objects
    if renames:
        single_visual["columnProperties"] = {qr: {"displayName": dn} for qr, dn in renames.items()}
    if extra_config:
        single_visual.update(extra_config)

    config = {
        "name": vis_name,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "width": w, "height": h,
                                            "z": z, "tabOrder": z}}],
        "singleVisual": single_visual,
    }

    return {
        "x": x, "y": y, "z": z,
        "width": w, "height": h,
        "config": jdump(config),
        "filters": jdump(vfilters) if vfilters else "[]",
    }


def _textbox(x, y, w, h, text, font_size="18", bold=True):
    """Title textbox visual."""
    vis_name = str(uuid.uuid4())[:8]
    z = _next_z()
    weight = "bold" if bold else "normal"
    config = {
        "name": vis_name,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "width": w, "height": h,
                                            "z": z, "tabOrder": z}}],
        "singleVisual": {
            "visualType": "textbox",
            "objects": {
                "general": [{
                    "properties": {
                        "paragraphs": [{
                            "textRuns": [{
                                "value": text,
                                "textRunStyle": {
                                    "fontWeight": weight,
                                    "fontFamily": "Segoe UI Semibold",
                                    "fontSize": f"{font_size}pt",
                                    "color": {"solid": {"color": "#1F4E79"}},
                                },
                            }],
                            "paragraphStyle": {"textAnchor": "Middle"},
                        }]
                    }
                }]
            },
        },
    }
    return {"x": x, "y": y, "z": z, "width": w, "height": h,
            "config": jdump(config), "filters": "[]"}


def _card(x, y, w, h, measure, title=None):
    return _visual_container(x, y, w, h, "card",
        [("Values", "_Measures", measure, True)], title=title, objects=_card_objects())


def _line(x, y, w, h, cat_table, cat_col, y_specs, series_table=None,
          series_col=None, title=None, vfilters=None, cat_values=None):
    """y_specs: list of (table, col, is_measure). cat_values: the series values to
    colour distinctly (one palette colour each), avoiding look-alike spaghetti lines."""
    proj = [("Category", cat_table, cat_col, False)]
    for tbl, col, is_m in y_specs:
        proj.append(("Y", tbl, col, is_m))
    if series_table:
        proj.append(("Series", series_table, series_col, False))
    # Single-series lines get the accent colour; split lines colour each series
    # distinctly from the categorical palette and show a top legend.
    cat_dp = _cat_dp(series_table, series_col, cat_values) if (series_table and cat_values) else None
    objs = _chart_objects(accent=None if series_table else PRIMARY,
                          legend=bool(series_table), data_labels=False, cat_dp=cat_dp)
    return _visual_container(x, y, w, h, "lineChart", proj, title=title,
                             objects=objs, vfilters=vfilters)


def _bar(x, y, w, h, cat_table, cat_col, val_table, val_col, is_measure=False,
         series_table=None, series_col=None, title=None, horizontal=False, vfilters=None,
         sort_by_value=True):
    vtype = "clusteredBarChart" if horizontal else "clusteredColumnChart"
    proj = [
        ("Category", cat_table, cat_col, False),
        ("Y", val_table, val_col, is_measure),
    ]
    if series_table:
        proj.append(("Series", series_table, series_col, False))
    objs = _chart_objects(accent=None if series_table else PRIMARY,
                          legend=bool(series_table), data_labels=True)
    # Sort categories by value (largest first) so the ranking reads top-to-bottom.
    sort = ("Y", "desc") if sort_by_value else None
    return _visual_container(x, y, w, h, vtype, proj, title=title,
                             objects=objs, vfilters=vfilters, sort=sort)


def _area(x, y, w, h, cat_table, cat_col, y_specs, series_table=None,
          series_col=None, title=None, vfilters=None, value_names=None):
    """value_names: optional list of friendly legend labels aligned to y_specs."""
    proj = [("Category", cat_table, cat_col, False)]
    for tbl, col, is_m in y_specs:
        proj.append(("Y", tbl, col, is_m))
    if series_table:
        proj.append(("Series", series_table, series_col, False))
    # Colour the measure series explicitly (primary, secondary, …) for an on-brand look.
    palette = [PRIMARY, SECONDARY, "#5DA271", "#E1A730"]
    series_colors = [(_agg_ref(tbl, col), palette[i % len(palette)])
                     for i, (tbl, col, is_m) in enumerate(y_specs) if not is_m]
    renames = None
    if value_names:
        renames = {_agg_ref(tbl, col): value_names[i]
                   for i, (tbl, col, is_m) in enumerate(y_specs) if not is_m and i < len(value_names)}
    objs = _chart_objects(legend=True, data_labels=False, series_colors=series_colors)
    return _visual_container(x, y, w, h, "areaChart", proj, title=title,
                             objects=objs, vfilters=vfilters, renames=renames)


def _map_visual(x, y, w, h, location_table, location_col, size_table, size_col,
                is_measure=False, title=None, vfilters=None):
    proj = [
        ("Location", location_table, location_col, False),
        ("Size",     size_table,     size_col,     is_measure),
    ]
    return _visual_container(x, y, w, h, "map", proj, title=title,
                             objects=_map_objects(), vfilters=vfilters)


def _donut(x, y, w, h, cat_table, cat_col, val_table, val_col, is_measure=False,
           title=None, vfilters=None, cat_values=None):
    """Donut chart — Legend = cat_col, Values = val_col (aggregated in the Y slot).
    cat_values get distinct palette colours so the slices are tellable apart."""
    proj = [("Category", cat_table, cat_col, False), ("Y", val_table, val_col, is_measure)]
    objs = {
        "legend": [{"properties": {"show": _bool(True), "position": _pe("'Right'"),
                                   "showTitle": _bool(False), "labelColor": _color(MUTED),
                                   "fontSize": _pe("9D")}}],
        "labels": [{"properties": {"show": _bool(True), "color": _color(TEXT), "fontSize": _pe("9D"),
                                   "labelStyle": _pe("'Category, percent of total'")}}],
    }
    if cat_values:
        objs["dataPoint"] = _cat_dp(cat_table, cat_col, cat_values)
    return _visual_container(x, y, w, h, "donutChart", proj, title=title,
                             objects=objs, vfilters=vfilters)


def _page_navigator(x, y, w, h):
    """Built-in Page Navigator — auto-renders a button per report page and handles
    navigation; no data fields required."""
    vis_name = str(uuid.uuid4())[:8]
    z = _next_z()
    single_visual = {
        "visualType": "pageNavigator",
        "prototypeQuery": {"Version": 2, "From": [], "Select": []},
        "drillFilterOtherVisuals": True,
    }
    config = {"name": vis_name,
              "layouts": [{"id": 0, "position": {"x": x, "y": y, "width": w, "height": h,
                                                 "z": z, "tabOrder": z}}],
              "singleVisual": single_visual}
    return {"x": x, "y": y, "z": z, "width": w, "height": h,
            "config": jdump(config), "filters": "[]"}


def _table_visual(x, y, w, h, columns, title=None, vfilters=None, renames=None):
    """columns: list of (table, col, is_measure). renames: {col: friendly header}."""
    proj = [("Values", t, c, m) for t, c, m in columns]
    qr_renames = None
    if renames:
        qr_renames = {(f"{t}.[{c}]" if m else f"{t}.{c}"): renames[c]
                      for t, c, m in columns if c in renames}
    return _visual_container(x, y, w, h, "tableEx", proj, title=title,
                             objects=_table_objects(), vfilters=vfilters, renames=qr_renames)


def _slicer(x, y, w, h, table, col, title=None):
    return _visual_container(x, y, w, h, "slicer",
        [("Field", table, col, False)], title=title)


# ── Page builders ─────────────────────────────────────────────────────────────

def _page(name: str, display_name: str, visuals: list, ordinal: int) -> dict:
    return {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "displayName": display_name,
        "ordinal": ordinal,
        # Visuals are laid out on a 1280×720 canvas. Pin the page size and force
        # "Fit to Page" (displayOption 1) so the whole canvas scales to the window
        # instead of rendering at actual size and clipping right-edge visuals.
        "width": 1280,
        "height": 720,
        "displayOption": 1,
        "visualContainers": visuals,
        "config": jdump({
            "relationships": [],
            "objects": {
                "outspacePane": [{"properties": {"expanded": {"expr": {"Literal": {"Value": "false"}}}}}],
                "background":   [{"properties": {"color":    {"solid": {"color": PAGE_BG}},
                                                 "transparency": {"expr": {"Literal": {"Value": "0"}}}}}],
            }
        }),
        "filters": "[]",
    }


def _page_overview() -> dict:
    # 1280 × 720 canvas
    visuals = [
        _textbox(20, 12, 430, 44, "Australian Labour Market — Overview", font_size="18"),
        _page_navigator(470, 14, 390, 40),
        _slicer(880, 12, 380, 44, "DateTable", "Date"),

        # Unemployment trend line chart
        _line(20, 72, 860, 290,
              "DateTable", "Date",
              [("NationalOverview", "unemployment_rate_pct", False)],
              title="Unemployment Rate Trend (Seasonally Adjusted)"),

        # KPI cards — row 1
        _card(900, 72,  180, 120, "Latest Unemployment Rate",  title="Unemployment Rate"),
        _card(1090, 72, 178, 120, "Latest Employed Thousands", title="Employed ('000)"),

        # KPI cards — row 2
        _card(900, 202,  180, 120, "Latest Participation Rate", title="Participation Rate"),
        _card(1090, 202, 178, 120, "Latest Emp To Pop Ratio",   title="Emp-to-Pop Ratio"),

        # Employed persons trend
        _line(20, 378, 860, 310,
              "DateTable", "Date",
              [("NationalOverview", "employed_thousands", False)],
              title="Employed Persons ('000, Seasonally Adjusted)"),

        # MoM / YoY change cards
        _card(900, 378, 180, 120, "Unemployment Rate MoM Change", title="Unemp. Rate MoM Δ"),
        _card(1090, 378, 178, 120, "Employed YoY Change Pct",     title="Employed YoY %"),
    ]
    return _page("ReportSection1", "Overview", visuals, 0)


def _page_state() -> dict:
    visuals = [
        _textbox(20, 12, 700, 44, "State Breakdown — Unemployment & Employment", font_size="18"),
        _page_navigator(740, 14, 520, 40),

        # Ranked bar: unemployment rate by state, latest month (sorted high→low).
        # The bubble map was dropped — it rendered as a zoomed-out world map and read
        # as "broken"; the ranked bars tell the state story cleanly and reliably.
        _bar(20, 72, 610, 300,
             "UnemploymentByState", "region_name",
             "UnemploymentByState", "unemployment_rate_pct",
             title="Unemployment Rate by State — Latest Month (%)",
             horizontal=True,
             vfilters=[_categorical_filter("UnemploymentByState", "is_latest_month", [1])]),

        # Ranked bar: employed persons by state, latest month.
        _bar(650, 72, 610, 300,
             "UnemploymentByState", "region_name",
             "UnemploymentByState", "employed_thousands",
             title="Employed Persons by State — Latest Month ('000)",
             horizontal=True,
             vfilters=[_categorical_filter("UnemploymentByState", "is_latest_month", [1])]),

        # State unemployment trend — one distinctly-coloured line per state.
        _line(20, 392, 1240, 300,
              "DateTable", "Date",
              [("UnemploymentByState", "unemployment_rate_pct", False)],
              series_table="UnemploymentByState", series_col="region_name",
              title="Unemployment Rate Trend by State (%)",
              cat_values=STATES),
    ]
    return _page("ReportSection2", "State Breakdown", visuals, 1)


def _page_industry() -> dict:
    visuals = [
        _textbox(20, 12, 700, 44, "Industry View — Sector Employment", font_size="18"),
        _page_navigator(740, 14, 520, 40),

        # Horizontal bar: employed persons by industry, latest year only — one bar
        # per industry (without the filter, employed_thousands sums over every period).
        # Widened to 700px so long ANZSIC division names aren't truncated.
        _bar(20, 72, 700, 620,
             "IndustryBreakdown", "industry_name",
             "IndustryBreakdown", "employed_thousands",
             title="Employed Persons by Industry — 2022 ('000, annual)",
             horizontal=True,
             vfilters=[_categorical_filter("IndustryBreakdown", "is_latest_year", [1])]),

        # Line chart: focus industries over time — one line per focus industry
        # (is_focus_industry=1 → Construction, Health Care, Info Media, Retail).
        _line(740, 72, 520, 310,
              "DateTable", "Date",
              [("IndustryBreakdown", "employed_thousands", False)],
              series_table="IndustryBreakdown", series_col="industry_name",
              title="Employment Trend — Focus Industries (annual, to 2022)",
              vfilters=[_categorical_filter("IndustryBreakdown", "is_focus_industry", [1])],
              cat_values=FOCUS_INDUSTRIES),

        # Table: industry details, latest year only — one row per industry (without
        # the filter the table lists every period as a separate row).
        _table_visual(740, 400, 520, 292,
                      [
                          ("IndustryBreakdown", "industry_name",           False),
                          ("IndustryBreakdown", "employed_thousands",      False),
                          ("IndustryBreakdown", "employed_yoy_change_pct", False),
                          ("IndustryBreakdown", "growth_category",         False),
                      ],
                      title="Industry Detail",
                      vfilters=[_categorical_filter("IndustryBreakdown", "is_latest_year", [1])],
                      renames={"industry_name": "Industry", "employed_thousands": "Employed ('000)",
                               "employed_yoy_change_pct": "YoY change", "growth_category": "Growth"}),
    ]
    return _page("ReportSection3", "Industry View", visuals, 2)


def _page_ftpt() -> dict:
    visuals = [
        _textbox(20, 12, 700, 44, "Full-time vs Part-time Employment", font_size="18"),
        _page_navigator(740, 14, 520, 40),

        # Stacked area: FT + PT over time. Filter to Persons only — sex_label holds
        # {Persons, Male, Female} where Persons = Male + Female, so summing all three
        # double-counts the totals.
        _area(20, 72, 800, 300,
              "DateTable", "Date",
              [
                  ("FulltimeParttime", "employed_fulltime_thousands", False),
                  ("FulltimeParttime", "employed_parttime_thousands", False),
              ],
              title="Full-time vs Part-time Employed — Persons ('000)",
              vfilters=[_categorical_filter("FulltimeParttime", "sex_label", ["Persons"])],
              value_names=["Full-time", "Part-time"]),

        # KPI cards
        _card(840, 72,  200, 130, "Latest FT Share Persons", title="Full-time Share"),
        _card(1050, 72, 210, 130, "Latest PT Share Persons", title="Part-time Share"),
        _card(840, 212, 200, 130, "FT Share YoY Change",     title="FT Share YoY Δ"),

        # Line: FT share % by sex — one line per sex (series = sex_label); without it
        # the share averages across all three labels into a single blended line.
        _line(20, 390, 800, 298,
              "DateTable", "Date",
              [("FulltimeParttime", "fulltime_share_pct", False)],
              series_table="FulltimeParttime", series_col="sex_label",
              title="Full-time Share (%) by Sex Over Time",
              cat_values=SEXES),

        # Donut: total employment share by sex, latest month only. Exclude the
        # "Persons" total (= Male + Female) so the two slices are genuine sex splits.
        _donut(840, 352, 420, 336,
               "FulltimeParttime", "sex_label",
               "FulltimeParttime", "employed_total_thousands",
               title="Employment by Sex (Latest Month)",
               vfilters=[
                   _categorical_filter("FulltimeParttime", "sex_label", ["Persons"], exclude=True),
                   _categorical_filter("FulltimeParttime", "is_latest_month", [1]),
               ],
               cat_values=["Male", "Female"]),
    ]
    return _page("ReportSection4", "Full-time vs Part-time", visuals, 3)


def _make_report() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "resourcePackages": [
            {"resourcePackage": {
                "name": "RegisteredResources",
                "type": 1,
                "items": [{"name": THEME_NAME, "path": f"{THEME_NAME}.json", "type": 202}],
                "disabled": False,
            }}
        ],
        "sections": [
            _page_overview(),
            _page_state(),
            _page_industry(),
            _page_ftpt(),
        ],
        "config": jdump({
            "objects": {},
            "defaultDrillFilterOtherVisuals": True,
            "themeCollection": {"customTheme": {"name": THEME_NAME, "type": 1}},
        }),
        "filters": "[]",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("Building aus_job_dashboard.pbip ...\n")

    # Project file
    write_json(BASE_DIR / "aus_job_dashboard.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": "aus_job_dashboard.Report"}}],
        "settings": {},
    })

    # Semantic model
    write_json(MODEL_DIR / "definition.pbism", {"version": "4.0", "settings": {}})
    write_json(MODEL_DIR / "model.bim", _make_model())

    # Report
    write_json(REPORT_DIR / "definition.pbir", {
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../aus_job_dashboard.SemanticModel"}},
    })
    write_json(REPORT_DIR / "report.json", _make_report())

    # Custom theme (registered resource referenced by report.json)
    write_json(REPORT_DIR / "StaticResources" / "RegisteredResources" / f"{THEME_NAME}.json",
               _theme_dict())

    print(f"\nBound to: {SERVER} / {DATABASE}  (schema: mart)")
    print("\nDone. Next steps:")
    print("  1. Make sure the warehouse is built: py -3 run_pipeline.py")
    print("  2. Open: powerbi/aus_job_dashboard.pbip in Power BI Desktop")
    print("  3. Click Refresh All")
    print("\n  Close Desktop WITHOUT saving before regenerating — saving from")
    print("  Desktop overwrites these generated files.")


if __name__ == "__main__":
    main()
