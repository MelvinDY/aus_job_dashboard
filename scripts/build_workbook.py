"""
build_workbook.py — Generate excel/aus_labour_market.xlsx.

The workbook is generated, not hand-built, for the same reason the Power BI
report is: it can then be regenerated from source rather than being a binary
nobody can review or reproduce.

Three sheets read the mart export through Power Query, plus a PivotTable and a
slicer on the sheet carrying the project's headline finding.

HOW THE REFRESH STAYS PORTABLE
    Power Query has no notion of a relative path, so a workbook with
    C:\\Users\\someone\\... baked into its queries stops refreshing the moment
    anyone clones the repo somewhere else. Instead, the named cell `DataFolder`
    holds this formula:

        =LEFT(CELL("filename",$A$1), FIND("[", CELL("filename",$A$1)) - 1) & "data\\"

    which resolves to the workbook's own folder at open time, and every query
    reads its path from that cell. Move the repo anywhere and refresh still
    works.

Requires Excel installed (COM automation) — this script only needs to run when
the workbook's structure changes, not on every pipeline run. The committed
.xlsx is the deliverable.

Run: py -3 scripts/build_workbook.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCEL_DIR = ROOT / "excel"
DATA_DIR = EXCEL_DIR / "data"
OUT = EXCEL_DIR / "aus_labour_market.xlsx"

# ── Excel constants (COM has no enums from Python) ──────────────────────────
xlSrcExternal, xlCmdSql = 0, 2
xlDatabase, xlRowField, xlColumnField = 1, 1, 2
xlAverage = -4106
xlWorkbookDefault = 51
xlDescending = 2

ACCENT = 0x795E1F   # BGR for #1F4E79 — COM colours are BGR, not RGB
MUTED = 0x7B6B5B


def m_type(col: str) -> str:
    """Map a mart column name to its Power Query type."""
    if col == "date":
        return "type date"
    if col.startswith("is_") or col.startswith("rank_"):
        return "Int64.Type"
    if col.endswith(("_pct", "_ppt", "_thousands")):
        return "type number"
    return "type text"


def csv_columns(stem: str) -> list[str]:
    """Read the exported file's header — the mart contract, straight from the file."""
    path = DATA_DIR / f"{stem}.csv"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found — run: py -3 run_pipeline.py")
    header = path.read_text(encoding="utf-8-sig").splitlines()[0]
    return header.split(",")


def m_query(stem: str, extra_steps: list[str] = None, final: str = None) -> str:
    """
    Build the M for one query: read the CSV from the folder named in DataFolder,
    promote headers, type every column, then apply any query-specific steps.
    """
    cols = csv_columns(stem)
    types = ", ".join('{"' + c + '", ' + m_type(c) + "}" for c in cols)
    steps = [
        "let",
        '    // Resolve the data folder from the workbook\'s own location, so the',
        '    // refresh keeps working wherever this repo is cloned.',
        '    DataFolder = Excel.CurrentWorkbook(){[Name="DataFolder"]}[Content]{0}[Column1],',
        f'    Source = Csv.Document(File.Contents(DataFolder & "{stem}.csv"),'
        f' [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f"    Typed = Table.TransformColumnTypes(Promoted, {{{types}}})",
    ]
    if extra_steps:
        steps[-1] += ","
        steps.extend(extra_steps)
    steps.append("in")
    steps.append(f"    {final or 'Typed'}")
    return "\n".join(steps)


def main() -> None:
    try:
        import win32com.client as win32
    except ImportError:
        sys.exit("ERROR: pywin32 is required to build the workbook.\n"
                 "       py -3 -m pip install pywin32")

    if not DATA_DIR.exists():
        sys.exit(f"ERROR: {DATA_DIR} not found — run: py -3 run_pipeline.py")

    print("Building excel/aus_labour_market.xlsx ...\n")

    # ── Queries ─────────────────────────────────────────────────────────────
    queries = {
        "National trend": m_query("national_overview"),

        # A comparison, not a dump: the latest month only, ranked worst-first.
        # Doing this in M rather than in the sheet keeps it part of the refresh.
        "State comparison": m_query(
            "unemployment_by_state",
            extra_steps=[
                "    Latest = Table.SelectRows(Typed, each [is_latest_month] = 1),",
                '    Ranked = Table.Sort(Latest, {{"unemployment_rate_pct", Order.Descending}}),',
                '    Trimmed = Table.SelectColumns(Ranked, {"date", "region_name",'
                ' "unemployment_rate_pct", "employed_thousands",'
                ' "unemployment_rate_yoy_change_ppt", "employed_yoy_change_pct"})',
            ],
            final="Trimmed",
        ),

        # `year` is added here so the PivotTable can group by it.
        "Full-time vs part-time by sex": m_query(
            "fulltime_parttime",
            extra_steps=[
                '    WithYear = Table.AddColumn(Typed, "year", each Date.Year([date]),'
                " Int64.Type)",
            ],
            final="WithYear",
        ),
    }

    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        wb = excel.Workbooks.Add()
        # Start from exactly one sheet; the rest are added in order below.
        while wb.Sheets.Count > 1:
            wb.Sheets(wb.Sheets.Count).Delete()

        # ── Read me sheet (also hosts the DataFolder cell) ──────────────────
        info = wb.Sheets(1)
        info.Name = "Read me"
        rows = [
            ("Australian Labour Market — ABS Labour Force", True, 16),
            ("", False, 11),
            ("Source: Australian Bureau of Statistics, Labour Force survey and "
             "Labour Account, via the ABS Data API.", False, 11),
            ("Built by a dbt star schema on SQL Server; these sheets read the "
             "mart export in excel/data.", False, 11),
            ("", False, 11),
            ("To refresh: Data > Refresh All. See excel/README.md.", True, 11),
            ("", False, 11),
            ("READ THIS BEFORE QUOTING THE STATE SHEET", True, 12),
            ("State figures are the ABS TREND series, not seasonally adjusted.", False, 11),
            ("The ABS publishes no seasonally adjusted series for the Northern "
             "Territory or the ACT, so a", False, 11),
            ("seasonally adjusted comparison silently covers only six of the eight "
             "jurisdictions. Trend exists", False, 11),
            ("for all eight, which is what makes ranking them against each other "
             "valid. The trade-off is that", False, 11),
            ("these rates will NOT match the seasonally adjusted headline rate "
             "quoted in the news.", False, 11),
            ("", False, 11),
            ("Industry data (in Power BI, not this workbook) is ANNUAL and lags "
             "the monthly survey by years:", False, 11),
            ("the Labour Force survey has no industry dimension, so it comes from "
             "the annual Labour Account.", False, 11),
        ]
        for i, (text, bold, size) in enumerate(rows, start=1):
            cell = info.Cells(i, 1)
            cell.Value = text
            cell.Font.Bold = bold
            cell.Font.Size = size
            if i == 1:
                cell.Font.Color = ACCENT
        info.Columns(1).ColumnWidth = 100

        # The portable-path cell: a formula resolving to this workbook's folder.
        info.Range("A20").Value = "Data folder (resolved automatically):"
        info.Range("A20").Font.Bold = True
        anchor = info.Range("A21")
        anchor.Formula = (
            '=LEFT(CELL("filename",$A$1),FIND("[",CELL("filename",$A$1))-1)&"data\\"'
        )
        anchor.Font.Color = MUTED
        wb.Names.Add(Name="DataFolder", RefersTo="='Read me'!$A$21")

        # The workbook must exist on disk before CELL("filename") returns a path,
        # and the queries read that cell — so save before adding them.
        OUT.parent.mkdir(parents=True, exist_ok=True)
        if OUT.exists():
            OUT.unlink()
        wb.SaveAs(str(OUT), FileFormat=xlWorkbookDefault)
        excel.CalculateFull()
        print(f"  DataFolder resolves to: {anchor.Value}")

        # ── Queries -> sheets ───────────────────────────────────────────────
        for name, formula in queries.items():
            wb.Queries.Add(Name=name, Formula=formula)
            print(f"  query: {name}")

        sheet_for = {
            "National trend": "National trend",
            "State comparison": "State comparison",
            "Full-time vs part-time by sex": "FT vs PT by sex",
        }
        tables = {}
        for query_name, sheet_name in sheet_for.items():
            ws = wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
            ws.Name = sheet_name

            conn = ("OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=$Workbook$;"
                    f"Location={query_name};Extended Properties=\"\"")
            lo = ws.ListObjects.Add(
                SourceType=xlSrcExternal, Source=conn, Destination=ws.Range("A1")
            )
            lo.QueryTable.CommandType = xlCmdSql
            lo.QueryTable.CommandText = f"SELECT * FROM [{query_name}]"
            lo.QueryTable.BackgroundQuery = False
            lo.QueryTable.Refresh(BackgroundQuery=False)
            lo.Name = query_name.replace(" ", "_").replace("-", "_")
            tables[query_name] = (ws, lo)

            ws.Rows(1).Font.Bold = True
            ws.Range("A2").Select()
            excel.ActiveWindow.FreezePanes = True
            ws.Columns.AutoFit()
            for c in range(1, lo.ListColumns.Count + 1):
                if ws.Columns(c).ColumnWidth < 12:
                    ws.Columns(c).ColumnWidth = 12
            print(f"  sheet: {sheet_name}  ({lo.ListRows.Count:,} rows)")

        # ── PivotTable + slicer, on the headline finding ────────────────────
        ftpt_ws, ftpt_lo = tables["Full-time vs part-time by sex"]
        pivot_ws = wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
        pivot_ws.Name = "FT share pivot"

        pivot_ws.Range("A1").Value = "Full-time share of employment, by sex"
        pivot_ws.Range("A1").Font.Bold = True
        pivot_ws.Range("A1").Font.Size = 14
        pivot_ws.Range("A1").Font.Color = ACCENT
        pivot_ws.Range("A2").Value = (
            "The headline finding: about 80% of employed men work full-time, "
            "against about 57% of employed women."
        )
        pivot_ws.Range("A3").Value = "Use the slicer to isolate one group. Seasonally adjusted, persons aged 15+."
        pivot_ws.Range("A3").Font.Color = MUTED

        cache = wb.PivotCaches().Create(SourceType=xlDatabase, SourceData=ftpt_lo.Range)
        pt = cache.CreatePivotTable(
            TableDestination=pivot_ws.Range("A6"), TableName="FTSharePivot"
        )
        pt.PivotFields("year").Orientation = xlRowField
        pt.PivotFields("year").AutoSort(xlDescending, "year")
        pt.PivotFields("sex_label").Orientation = xlColumnField
        field = pt.AddDataField(
            pt.PivotFields("fulltime_share_pct"), "Full-time share %", xlAverage
        )
        field.NumberFormat = "0.0"
        pt.TableStyle2 = "PivotStyleMedium2"

        slicer_cache = wb.SlicerCaches.Add2(pt, "sex_label")
        # Keyword args, so the optional `Level` (OLAP-only) is genuinely omitted
        # rather than passed as an empty value, which the API rejects.
        slicer_cache.Slicers.Add(
            SlicerDestination=pivot_ws, Name="Sex", Caption="Sex",
            Top=90, Left=340, Width=150, Height=130,
        )
        print("  sheet: FT share pivot  (PivotTable + slicer)")

        info.Activate()
        wb.Save()
        print(f"\nWrote: {OUT.relative_to(ROOT)}")

    finally:
        try:
            wb.Close(SaveChanges=False)
        except Exception:
            pass
        excel.Quit()


if __name__ == "__main__":
    main()
