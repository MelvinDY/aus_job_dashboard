"""
export_mart.py — Publish the mart views as the Excel workbook's refresh source.

Reads:   SQL Server — schema: mart  (built by dbt)
Writes:  excel/data/*.csv

Why a file export rather than pointing Excel straight at SQL Server: the
workbook is a portfolio deliverable, and someone opening it should not need
Docker running, a driver installed, or a password to see anything. The CSVs are
committed, so the workbook opens and refreshes on a clean clone; the pipeline
rewrites them whenever the models rebuild.

That makes this export a contract. The column names here are the ones the
workbook's Power Query steps reference by name, so changing a mart column
renames a column in the workbook — which is exactly why every mart column is
documented and tested in dbt rather than being free to drift.

Run: py -3 scripts/export_mart.py
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "excel" / "data"

sys.path.insert(0, str(ROOT / "scripts"))
from load_raw import build_conn_str  # noqa: E402  — one definition of the connection

# Mart view -> exported file. One file per dashboard page, plus the star schema's
# dimensions, so the workbook can demonstrate a join rather than only flat reads.
EXPORTS = {
    "mart.v_national_overview":     ("national_overview",     "date"),
    "mart.v_unemployment_by_state": ("unemployment_by_state", "region_name, date"),
    "mart.v_fulltime_parttime":     ("fulltime_parttime",     "sex_label, date"),
    "mart.v_industry_breakdown":    ("industry_breakdown",    "industry_name, date"),
}


def main() -> None:
    print("=== Export mart to excel/data ===\n")

    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={build_conn_str()}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        print(f"ERROR: could not connect to the warehouse.\n{e}\n")
        print("Is it running?  docker compose up -d")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    for view, (stem, order_by) in EXPORTS.items():
        df = pd.read_sql(f"SELECT * FROM {view} ORDER BY {order_by}", engine)

        # Excel reads a date far more reliably as an ISO string than as whatever
        # the driver hands back; Power Query types it on the way in.
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime("%Y-%m-%d")

        out = OUT_DIR / f"{stem}.csv"
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"  {view:<32} -> excel/data/{stem}.csv  ({len(df):,} rows, {df.shape[1]} cols)")
        total += len(df)

    print(f"\n=== Done: {total:,} rows exported ===")


if __name__ == "__main__":
    main()
