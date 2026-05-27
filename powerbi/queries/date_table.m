// Query: DateTable
// Standalone date dimension — mark as Date Table in Power BI (right-click > Mark as date table > date)
// Enables native time intelligence: DATEADD, SAMEPERIODLASTYEAR, etc.
// Covers 1978-01-01 to today.

let
    StartDate  = #date(1978, 1, 1),
    EndDate    = Date.From(DateTime.LocalNow()),
    DayCount   = Duration.Days(EndDate - StartDate) + 1,

    DateList   = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),
    DateTable  = Table.FromList(DateList, Splitter.SplitByNothing(), {"date"}),

    #"Date type" = Table.TransformColumnTypes(DateTable, {{"date", type date}}),

    #"Add Year"        = Table.AddColumn(#"Date type",   "year",          each Date.Year([date]),          Int64.Type),
    #"Add MonthNum"    = Table.AddColumn(#"Add Year",    "month_number",  each Date.Month([date]),         Int64.Type),
    #"Add MonthName"   = Table.AddColumn(#"Add MonthNum","month_name",    each Date.ToText([date], "MMM"), type text),
    #"Add MonthShort"  = Table.AddColumn(#"Add MonthName","month_year",   each Date.ToText([date], "MMM yyyy"), type text),
    #"Add Quarter"     = Table.AddColumn(#"Add MonthShort","quarter",     each "Q" & Text.From(Date.QuarterOfYear([date])), type text),
    #"Add FY"          = Table.AddColumn(#"Add Quarter", "financial_year",
                            // Australian financial year: Jul–Jun, e.g. Jul 2023–Jun 2024 = "FY2024"
                            each if Date.Month([date]) >= 7
                                 then "FY" & Text.From(Date.Year([date]) + 1)
                                 else "FY" & Text.From(Date.Year([date])),
                            type text),
    #"Add FYSort"      = Table.AddColumn(#"Add FY", "financial_year_sort",
                            each if Date.Month([date]) >= 7
                                 then Date.Year([date]) + 1
                                 else Date.Year([date]),
                            Int64.Type),
    #"Add IsFirstOfMonth" = Table.AddColumn(#"Add FYSort", "is_first_of_month",
                            each if Date.Day([date]) = 1 then 1 else 0, Int64.Type)
in
    #"Add IsFirstOfMonth"
