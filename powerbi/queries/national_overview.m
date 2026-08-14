// Query: NationalOverview
// Mart view: mart.v_national_overview
// Dashboard page: Overview — trend line + KPI cards

let
    Source = Sql.Database(
        "localhost,1433",
        "aus_job_dashboard",
        [Query = "SELECT * FROM mart.v_national_overview ORDER BY date"]
    ),
    #"Changed Types" = Table.TransformColumnTypes(Source, {
        {"date",                           type date},
        {"employed_thousands",             type number},
        {"unemployed_thousands",           type number},
        {"unemployment_rate_pct",          type number},
        {"participation_rate_pct",         type number},
        {"emp_to_pop_ratio_pct",           type number},
        {"unemployment_rate_mom_change_ppt", type number},
        {"employed_mom_change_pct",        type number},
        {"unemployment_rate_yoy_change_ppt", type number},
        {"employed_yoy_change_pct",        type number},
        {"is_latest_month",                Int64.Type}
    })
in
    #"Changed Types"
