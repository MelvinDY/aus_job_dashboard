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
  1. Complete the full pipeline: extract → transform → load → deploy_views.sql
  2. Set SERVER and DATABASE below to your Azure SQL values
  3. Run: python powerbi/build_report.py
  4. Open powerbi/aus_job_dashboard.pbip in Power BI Desktop
  5. Sign in to Azure SQL when prompted, then click Refresh
"""

import json
import uuid
from pathlib import Path

# ── Configure before running ─────────────────────────────────────────────────
SERVER   = "<your-server>.database.windows.net"
DATABASE = "<your-database>"
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


def _m_table(name: str, sql: str, columns: list) -> dict:
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
        cols.append(col)
    return {
        "name": name,
        "columns": cols,
        "partitions": [{
            "name": "Partition",
            "mode": "import",
            "source": {"type": "m", "expression": expression},
        }],
    }


def _make_model() -> dict:
    # ── Column specs ──────────────────────────────────────────────────────────
    def c(name, dtype, mtype, fmt=None, hidden=False):
        return {"name": name, "dataType": dtype, "mtype": mtype,
                "fmt": fmt, "hidden": hidden}

    national_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("employed_thousands",            "double",   "type number", "#,0.0"),
        c("unemployed_thousands",          "double",   "type number", "#,0.0"),
        c("unemployment_rate_pct",         "double",   "type number", "0.00"),
        c("participation_rate_pct",        "double",   "type number", "0.00"),
        c("emp_to_pop_ratio_pct",          "double",   "type number", "0.00"),
        c("unemployment_rate_mom_change_ppt", "double","type number", "+0.000;-0.000"),
        c("employed_mom_change_pct",       "double",   "type number", "+0.00;-0.00"),
        c("unemployment_rate_yoy_change_ppt","double", "type number", "+0.000;-0.000"),
        c("employed_yoy_change_pct",       "double",   "type number", "+0.00;-0.00"),
        c("is_latest_month",               "int64",    "Int64.Type",  hidden=True),
    ]
    state_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("region_code",                   "string",   "type text"),
        c("region_name",                   "string",   "type text"),
        c("employed_thousands",            "double",   "type number", "#,0.0"),
        c("unemployment_rate_pct",         "double",   "type number", "0.00"),
        c("unemployment_rate_mom_change_ppt","double", "type number", "+0.000;-0.000"),
        c("unemployment_rate_yoy_change_ppt","double", "type number", "+0.000;-0.000"),
        c("employed_yoy_change_pct",       "double",   "type number", "+0.00;-0.00"),
        c("is_latest_month",               "int64",    "Int64.Type",  hidden=True),
    ]
    industry_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("industry_code",                 "string",   "type text"),
        c("industry_name",                 "string",   "type text"),
        c("employed_thousands",            "double",   "type number", "#,0.0"),
        c("employed_yoy_change_thousands", "double",   "type number", "#,0.0"),
        c("employed_yoy_change_pct",       "double",   "type number", "+0.00;-0.00"),
        c("rank_by_employment",            "int64",    "Int64.Type"),
        c("growth_category",               "string",   "type text"),
        c("is_focus_industry",             "int64",    "Int64.Type",  hidden=True),
        c("is_latest_year",                "int64",    "Int64.Type",  hidden=True),
    ]
    ftpt_cols = [
        c("date",                          "dateTime", "type date",   "Short Date"),
        c("sex_code",                      "string",   "type text",   hidden=True),
        c("sex_label",                     "string",   "type text"),
        c("employed_fulltime_thousands",   "double",   "type number", "#,0.0"),
        c("employed_parttime_thousands",   "double",   "type number", "#,0.0"),
        c("employed_total_thousands",      "double",   "type number", "#,0.0"),
        c("fulltime_share_pct",            "double",   "type number", "0.00"),
        c("parttime_share_pct",            "double",   "type number", "0.00"),
        c("fulltime_share_yoy_change_ppt", "double",   "type number", "+0.000;-0.000"),
        c("employed_total_yoy_change_pct", "double",   "type number", "+0.00;-0.00"),
        c("is_latest_month",               "int64",    "Int64.Type",  hidden=True),
    ]

    # ── DateTable (calculated) ────────────────────────────────────────────────
    date_table = {
        "name": "DateTable",
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
                "type": "calculated",
                "expression": [
                    "ADDCOLUMNS(",
                    '    CALENDAR(DATE(1978,1,1), TODAY()),',
                    '    "year",             YEAR([Date]),',
                    '    "month_number",     MONTH([Date]),',
                    '    "month_name",       FORMAT([Date], "MMM"),',
                    '    "month_year",       FORMAT([Date], "MMM yyyy"),',
                    '    "quarter",          "Q" & FORMAT([Date], "Q"),',
                    '    "financial_year",   IF(MONTH([Date])>=7,',
                    '                          "FY"&TEXT(YEAR([Date])+1,"0"),',
                    '                          "FY"&TEXT(YEAR([Date]),"0")),',
                    '    "is_first_of_month",IF(DAY([Date])=1, 1, 0)',
                    ")",
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

    # ── DAX measures ──────────────────────────────────────────────────────────
    measures = [
        # Overview KPIs
        ("Latest Unemployment Rate",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[unemployment_rate_pct]),NationalOverview[date]=D)',
         "0.00", "Overview KPIs"),
        ("Latest Employed Thousands",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[employed_thousands]),NationalOverview[date]=D)',
         "#,0.0", "Overview KPIs"),
        ("Latest Participation Rate",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[participation_rate_pct]),NationalOverview[date]=D)',
         "0.00", "Overview KPIs"),
        ("Latest Emp To Pop Ratio",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[emp_to_pop_ratio_pct]),NationalOverview[date]=D)',
         "0.00", "Overview KPIs"),
        ("Unemployment Rate MoM Change",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[unemployment_rate_mom_change_ppt]),NationalOverview[date]=D)',
         "+0.000;-0.000", "Overview KPIs"),
        ("Employed YoY Change Pct",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[employed_yoy_change_pct]),NationalOverview[date]=D)',
         "+0.00;-0.00", "Overview KPIs"),
        ("Unemployment Rate Subtitle",
         'VAR Ch=[Unemployment Rate MoM Change] VAR Ar=IF(Ch>0,"▲",IF(Ch<0,"▼","–")) RETURN Ar&" "&FORMAT(ABS(Ch),"0.0")&" ppt vs last month"',
         None, "Overview KPIs"),
        ("Employed Subtitle",
         'VAR Ch=[Employed YoY Change Pct] VAR Ar=IF(Ch>0,"▲",IF(Ch<0,"▼","–")) RETURN Ar&" "&FORMAT(ABS(Ch),"0.0")&"% vs last year"',
         None, "Overview KPIs"),
        # State KPIs
        ("National Avg Unemployment Rate",
         'VAR D=MAX(NationalOverview[date]) RETURN CALCULATE(MAX(NationalOverview[unemployment_rate_pct]),NationalOverview[date]=D)',
         "0.00", "State KPIs"),
        # Industry KPIs
        ("Latest Industry Employed",
         'CALCULATE(MAX(IndustryBreakdown[employed_thousands]),IndustryBreakdown[is_latest_year]=1)',
         "#,0.0", "Industry KPIs"),
        ("Latest Industry YoY Change",
         'CALCULATE(MAX(IndustryBreakdown[employed_yoy_change_pct]),IndustryBreakdown[is_latest_year]=1)',
         "+0.00;-0.00", "Industry KPIs"),
        # FT/PT KPIs
        ('Latest FT Share Persons',
         'CALCULATE(MAX(FulltimeParttime[fulltime_share_pct]),FulltimeParttime[is_latest_month]=1,FulltimeParttime[sex_label]="Persons")',
         "0.00", "FT PT KPIs"),
        ('Latest PT Share Persons',
         'CALCULATE(MAX(FulltimeParttime[parttime_share_pct]),FulltimeParttime[is_latest_month]=1,FulltimeParttime[sex_label]="Persons")',
         "0.00", "FT PT KPIs"),
        ('FT Share YoY Change',
         'VAR D=MAX(FulltimeParttime[date]) RETURN CALCULATE(MAX(FulltimeParttime[fulltime_share_yoy_change_ppt]),FulltimeParttime[date]=D,FulltimeParttime[sex_label]="Persons")',
         "+0.000;-0.000", "FT PT KPIs"),
        ('FT Share Subtitle',
         'VAR Ch=[FT Share YoY Change] VAR Ar=IF(Ch>0,"▲",IF(Ch<0,"▼","–")) RETURN Ar&" "&FORMAT(ABS(Ch),"0.0")&" ppt vs last year"',
         None, "FT PT KPIs"),
    ]

    measure_defs = []
    for name, expr, fmt, folder in measures:
        m = {"name": name, "expression": expr, "displayFolder": folder}
        if fmt:
            m["formatString"] = fmt
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
        "columns": [{"name": "Placeholder", "dataType": "int64", "isHidden": True,
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
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-AU",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "tables": [
                date_table,
                _m_table("NationalOverview",
                         "SELECT * FROM mart.v_national_overview ORDER BY date",
                         national_cols),
                _m_table("UnemploymentByState",
                         "SELECT * FROM mart.v_unemployment_by_state ORDER BY region_name, date",
                         state_cols),
                _m_table("IndustryBreakdown",
                         "SELECT * FROM mart.v_industry_breakdown ORDER BY industry_name, date",
                         industry_cols),
                _m_table("FulltimeParttime",
                         "SELECT * FROM mart.v_fulltime_parttime ORDER BY sex_label, date",
                         ftpt_cols),
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


def _visual_container(x, y, w, h, visual_type, projections, title=None,
                       objects=None, extra_config=None):
    """
    Build a report visual container dict.
    projections: list of (slot, table, column_or_measure, is_measure)
    """
    vis_name = str(uuid.uuid4())[:8]
    z = _next_z()

    from_map = {}
    from_list = []
    select_list = []
    proj_map = {}

    for slot, table, field, is_measure in projections:
        alias = table[0].lower() + str(len(from_map))
        if table not in from_map:
            from_map[table] = alias
            from_list.append({"Name": alias, "Entity": table, "Type": 0})
        else:
            alias = from_map[table]

        src_ref = {"SourceRef": {"Source": alias}}
        query_ref = f"{table}.[{field}]" if is_measure else f"{table}.{field}"

        if is_measure:
            sel = {"Measure": {"Expression": src_ref, "Property": field}, "Name": query_ref}
        else:
            sel = {"Column": {"Expression": src_ref, "Property": field}, "Name": query_ref}
        select_list.append(sel)

        proj_entry = {"queryRef": query_ref, "active": True}
        if slot not in proj_map:
            proj_map[slot] = []
        proj_map[slot].append(proj_entry)

    proto_query = {
        "Version": 2,
        "From": from_list,
        "Select": select_list,
    }

    single_visual = {
        "visualType": visual_type,
        "projections": proj_map,
        "prototypeQuery": proto_query,
    }

    if title:
        single_visual.setdefault("visualContainerObjects", {})["title"] = [{
            "properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                           "show": {"expr": {"Literal": {"Value": "true"}}}}
        }]
    if objects:
        single_visual["objects"] = objects
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
        "filters": "[]",
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
                                    "fontSize": f"{font_size}pt",
                                    "color": {"solid": {"color": "#1F2D3D"}},
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
        [("Values", "_Measures", measure, True)], title=title)


def _line(x, y, w, h, cat_table, cat_col, y_specs, title=None):
    """y_specs: list of (table, col, is_measure)"""
    proj = [("Category", cat_table, cat_col, False)]
    for tbl, col, is_m in y_specs:
        proj.append(("Y", tbl, col, is_m))
    return _visual_container(x, y, w, h, "lineChart", proj, title=title)


def _bar(x, y, w, h, cat_table, cat_col, val_table, val_col, is_measure=False,
         series_table=None, series_col=None, title=None, horizontal=False):
    vtype = "clusteredBarChart" if horizontal else "clusteredColumnChart"
    proj = [
        ("Category", cat_table, cat_col, False),
        ("Y", val_table, val_col, is_measure),
    ]
    if series_table:
        proj.append(("Series", series_table, series_col, False))
    return _visual_container(x, y, w, h, vtype, proj, title=title)


def _area(x, y, w, h, cat_table, cat_col, y_specs, series_table=None, series_col=None, title=None):
    proj = [("Category", cat_table, cat_col, False)]
    for tbl, col, is_m in y_specs:
        proj.append(("Y", tbl, col, is_m))
    if series_table:
        proj.append(("Series", series_table, series_col, False))
    return _visual_container(x, y, w, h, "areaChart", proj, title=title)


def _map_visual(x, y, w, h, location_table, location_col, size_table, size_col,
                is_measure=False, title=None):
    proj = [
        ("Location", location_table, location_col, False),
        ("Size",     size_table,     size_col,     is_measure),
    ]
    return _visual_container(x, y, w, h, "map", proj, title=title)


def _table_visual(x, y, w, h, columns, title=None):
    """columns: list of (table, col, is_measure)"""
    proj = [("Values", t, c, m) for t, c, m in columns]
    return _visual_container(x, y, w, h, "tableEx", proj, title=title)


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
        "visualContainers": visuals,
        "config": jdump({
            "relationships": [],
            "objects": {
                "outspacePane": [{"properties": {"expanded": {"expr": {"Literal": {"Value": "false"}}}}}],
                "background":   [{"properties": {"color":    {"solid": {"color": "#F5F5F5"}},
                                                 "transparency": {"expr": {"Literal": {"Value": "0"}}}}}],
            }
        }),
        "filters": "[]",
    }


def _page_overview() -> dict:
    # 1280 × 720 canvas
    visuals = [
        _textbox(20, 12, 840, 44, "Australian Labour Market — Overview", font_size="18"),
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
        _textbox(20, 12, 1240, 44, "State Breakdown — Unemployment & Employment", font_size="18"),

        # Map: unemployment rate bubble by state
        _map_visual(20, 72, 600, 350,
                    "UnemploymentByState", "region_name",
                    "UnemploymentByState", "unemployment_rate_pct",
                    title="Unemployment Rate by State (Latest Month)"),

        # Bar chart: unemployment rate per state, latest month
        _bar(640, 72, 620, 350,
             "UnemploymentByState", "region_name",
             "UnemploymentByState", "unemployment_rate_pct",
             title="Unemployment Rate by State (Latest Month)",
             horizontal=True),

        # Line chart: state unemployment trends over time
        _line(20, 440, 1240, 258,
              "DateTable", "Date",
              [("UnemploymentByState", "unemployment_rate_pct", False)],
              title="State Unemployment Rate Trend"),
    ]
    return _page("ReportSection2", "State Breakdown", visuals, 1)


def _page_industry() -> dict:
    visuals = [
        _textbox(20, 12, 1240, 44, "Industry View — Sector Employment", font_size="18"),

        # Horizontal bar: employed persons by industry (latest year)
        _bar(20, 72, 560, 620,
             "IndustryBreakdown", "industry_name",
             "IndustryBreakdown", "employed_thousands",
             title="Employed Persons by Industry — Latest Year ('000)",
             horizontal=True),

        # Line chart: focus industries over time
        _line(600, 72, 660, 310,
              "DateTable", "Date",
              [("IndustryBreakdown", "employed_thousands", False)],
              title="Employment Trend — Focus Industries"),

        # Table: industry details
        _table_visual(600, 400, 660, 292,
                      [
                          ("IndustryBreakdown", "industry_name",           False),
                          ("IndustryBreakdown", "employed_thousands",      False),
                          ("IndustryBreakdown", "employed_yoy_change_pct", False),
                          ("IndustryBreakdown", "growth_category",         False),
                      ],
                      title="Industry Detail"),
    ]
    return _page("ReportSection3", "Industry View", visuals, 2)


def _page_ftpt() -> dict:
    visuals = [
        _textbox(20, 12, 1240, 44, "Full-time vs Part-time Employment", font_size="18"),

        # Stacked area: FT + PT over time (Persons)
        _area(20, 72, 800, 300,
              "DateTable", "Date",
              [
                  ("FulltimeParttime", "employed_fulltime_thousands", False),
                  ("FulltimeParttime", "employed_parttime_thousands", False),
              ],
              title="Full-time vs Part-time Employed — Persons ('000)"),

        # KPI cards
        _card(840, 72,  200, 130, "Latest FT Share Persons", title="Full-time Share"),
        _card(1050, 72, 210, 130, "Latest PT Share Persons", title="Part-time Share"),
        _card(840, 212, 200, 130, "FT Share YoY Change",     title="FT Share YoY Δ"),

        # Line: FT share % by sex
        _line(20, 390, 800, 298,
              "DateTable", "Date",
              [("FulltimeParttime", "fulltime_share_pct", False)],
              title="Full-time Share (%) by Sex Over Time"),

        # Clustered bar: FT vs PT by sex (latest month)
        _bar(840, 352, 420, 336,
             "FulltimeParttime", "sex_label",
             "FulltimeParttime", "employed_total_thousands",
             series_table="FulltimeParttime", series_col="sex_label",
             title="Employment by Sex (Latest Month)"),
    ]
    return _page("ReportSection4", "Full-time vs Part-time", visuals, 3)


def _make_report() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "resourcePackages": [],
        "sections": [
            _page_overview(),
            _page_state(),
            _page_industry(),
            _page_ftpt(),
        ],
        "config": jdump({
            "objects": {},
            "defaultDrillFilterOtherVisuals": True,
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
        "settings": {"enableTmdlSave": False, "enableAutoRecovery": False},
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

    print("\nDone. Next steps:")
    print("  1. Edit SERVER and DATABASE at the top of this script")
    print("  2. Re-run: python powerbi/build_report.py")
    print("  3. Open: powerbi/aus_job_dashboard.pbip in Power BI Desktop")
    print("  4. Sign in to Azure SQL, then click Refresh All")


if __name__ == "__main__":
    main()
