// Query: IndustryBreakdown
// Mart view: mart.v_industry_breakdown
// Dashboard page: Industry View — bar chart + line trend

let
    Source = Sql.Database(
        "localhost,1433",
        "aus_job_dashboard",
        [Query = "SELECT * FROM mart.v_industry_breakdown ORDER BY industry_name, date"]
    ),
    #"Changed Types" = Table.TransformColumnTypes(Source, {
        {"date",                             type date},
        {"industry_code",                    type text},
        {"industry_name",                    type text},
        {"employed_thousands",               type number},
        {"employed_yoy_change_thousands",    type number},
        {"employed_yoy_change_pct",          type number},
        {"rank_by_employment",               Int64.Type},
        {"growth_category",                  type text},
        {"is_focus_industry",                Int64.Type},
        {"is_latest_year",                   Int64.Type}
    })
in
    #"Changed Types"
