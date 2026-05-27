// Query: FulltimeParttime
// Mart view: mart.v_fulltime_parttime
// Dashboard page: Full-time vs Part-time — stacked area + bar

let
    Source = Sql.Database(
        "<your-server>.database.windows.net",
        "<your-database>",
        [Query = "SELECT * FROM mart.v_fulltime_parttime ORDER BY sex_label, date"]
    ),
    #"Changed Types" = Table.TransformColumnTypes(Source, {
        {"date",                              type date},
        {"sex_code",                          type text},
        {"sex_label",                         type text},
        {"employed_fulltime_thousands",       type number},
        {"employed_parttime_thousands",       type number},
        {"employed_total_thousands",          type number},
        {"fulltime_share_pct",                type number},
        {"parttime_share_pct",                type number},
        {"fulltime_share_yoy_change_ppt",     type number},
        {"employed_total_yoy_change_pct",     type number},
        {"is_latest_month",                   Int64.Type}
    })
in
    #"Changed Types"
