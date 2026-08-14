// Query: UnemploymentByState
// Mart view: mart.v_unemployment_by_state
// Dashboard page: State Breakdown — map + bar chart

let
    Source = Sql.Database(
        "localhost,1433",
        "aus_job_dashboard",
        [Query = "SELECT * FROM mart.v_unemployment_by_state ORDER BY region_name, date"]
    ),
    #"Changed Types" = Table.TransformColumnTypes(Source, {
        {"date",                                type date},
        {"region_code",                         type text},
        {"region_name",                         type text},
        {"employed_thousands",                  type number},
        {"unemployment_rate_pct",               type number},
        {"unemployment_rate_mom_change_ppt",    type number},
        {"unemployment_rate_yoy_change_ppt",    type number},
        {"employed_yoy_change_pct",             type number},
        {"is_latest_month",                     Int64.Type}
    })
in
    #"Changed Types"
