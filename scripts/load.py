"""
load.py — Load processed CSVs into Azure SQL staging tables.

Reads:   data/processed/*.csv  (output of transform.py)
Writes:  Azure SQL — schema: staging

Strategy: TRUNCATE then bulk INSERT (full refresh each run).
          Safe for a monthly dataset of this size (~10k total rows).

Requires:
  - pip install pyodbc sqlalchemy pandas python-dotenv
  - ODBC Driver 18 for SQL Server installed
  - .env file with AZURE_SQL_CONN_STR set

Table mapping:
  national_summary         → staging.national_summary
  state_summary            → staging.state_summary
  national_fulltime_parttime → staging.fulltime_parttime
  national_trend           → staging.national_trend
  industry_employment      → staging.industry_employment

Run: python scripts/load.py
"""

import sys
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# Each entry: (csv_filename_stem, staging_table_name, create_table_sql)
TABLES = [
    (
        "national_summary",
        "staging.national_summary",
        """
        CREATE TABLE staging.national_summary (
            date                      DATE          NOT NULL,
            employed_thousands        FLOAT         NULL,
            unemployed_thousands      FLOAT         NULL,
            participation_rate_pct    FLOAT         NULL,
            unemployment_rate_pct     FLOAT         NULL,
            emp_to_pop_ratio_pct      FLOAT         NULL,
            CONSTRAINT pk_national_summary PRIMARY KEY (date)
        )
        """,
    ),
    (
        "state_summary",
        "staging.state_summary",
        """
        CREATE TABLE staging.state_summary (
            date                      DATE          NOT NULL,
            region_code               NVARCHAR(10)  NOT NULL,
            region_name               NVARCHAR(100) NULL,
            employed_thousands        FLOAT         NULL,
            unemployment_rate_pct     FLOAT         NULL,
            CONSTRAINT pk_state_summary PRIMARY KEY (date, region_code)
        )
        """,
    ),
    (
        "national_fulltime_parttime",
        "staging.fulltime_parttime",
        """
        CREATE TABLE staging.fulltime_parttime (
            date                            DATE          NOT NULL,
            sex_code                        NVARCHAR(5)   NOT NULL,
            sex_label                       NVARCHAR(20)  NULL,
            employed_fulltime_thousands     FLOAT         NULL,
            employed_parttime_thousands     FLOAT         NULL,
            employed_total_thousands        FLOAT         NULL,
            fulltime_share_pct              FLOAT         NULL,
            parttime_share_pct              FLOAT         NULL,
            CONSTRAINT pk_fulltime_parttime PRIMARY KEY (date, sex_code)
        )
        """,
    ),
    (
        "national_trend",
        "staging.national_trend",
        """
        CREATE TABLE staging.national_trend (
            date                      DATE          NOT NULL,
            measure_code              NVARCHAR(10)  NOT NULL,
            measure_label             NVARCHAR(100) NULL,
            obs_value                 FLOAT         NULL,
            CONSTRAINT pk_national_trend PRIMARY KEY (date, measure_code)
        )
        """,
    ),
    (
        "industry_employment",
        "staging.industry_employment",
        """
        CREATE TABLE staging.industry_employment (
            date                            DATE          NOT NULL,
            industry_code                   NVARCHAR(10)  NOT NULL,
            industry_name                   NVARCHAR(100) NULL,
            employed_thousands              FLOAT         NULL,
            employed_yoy_change_thousands   FLOAT         NULL,
            employed_yoy_change_pct         FLOAT         NULL,
            CONSTRAINT pk_industry_employment PRIMARY KEY (date, industry_code)
        )
        """,
    ),
]

# Column rename map: processed CSV columns → staging table columns
COLUMN_RENAMES = {
    "REGION":       "region_code",
    "REGION_LABEL": "region_name",
    "SEX":          "sex_code",
    "SEX_LABEL":    "sex_label",
    "MEASURE":      "measure_code",
    "MEASURE_LABEL":"measure_label",
    "OBS_VALUE":    "obs_value",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_engine():
    conn_str = os.getenv("AZURE_SQL_CONN_STR")
    if not conn_str:
        print("ERROR: AZURE_SQL_CONN_STR not set in .env")
        sys.exit(1)

    # SQLAlchemy connection URL for pyodbc
    url = f"mssql+pyodbc:///?odbc_connect={conn_str}"
    return create_engine(url, fast_executemany=True)


def ensure_schema(engine) -> None:
    """Create the staging schema if it doesn't exist."""
    with engine.begin() as conn:
        conn.execute(text("IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'staging') EXEC('CREATE SCHEMA staging')"))


def ensure_table(engine, table: str, create_sql: str) -> None:
    """Create the table if it doesn't exist."""
    schema, tbl = table.split(".")
    check = text(f"""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{tbl}'
        )
        EXEC(:ddl)
    """)
    with engine.begin() as conn:
        conn.execute(check, {"ddl": create_sql.strip()})


def truncate_table(engine, table: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table}"))


def load_table(engine, df: pd.DataFrame, table: str) -> int:
    """Bulk insert DataFrame into table. Returns rows inserted."""
    schema, tbl = table.split(".")
    df.to_sql(
        name=tbl,
        con=engine,
        schema=schema,
        if_exists="append",
        index=False,
        chunksize=1000,
        method="multi",
    )
    return len(df)


def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns=COLUMN_RENAMES)
    # Ensure date column is a Python date (not Timestamp) for SQL Server
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== ABS Labour Force Load ===\n")

    engine = get_engine()

    # Verify connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connected to Azure SQL.\n")
    except SQLAlchemyError as e:
        print(f"ERROR: Could not connect to Azure SQL.\n{e}")
        sys.exit(1)

    ensure_schema(engine)

    success, failed = 0, []

    for csv_stem, table, create_sql in TABLES:
        print(f"[{table}]")
        csv_path = PROCESSED_DIR / f"{csv_stem}.csv"

        if not csv_path.exists():
            print(f"  SKIP: {csv_path} not found — run transform.py first.")
            failed.append(table)
            print()
            continue

        df = prepare_df(pd.read_csv(csv_path))
        print(f"  Loaded CSV: {len(df):,} rows")

        try:
            ensure_table(engine, table, create_sql)
            truncate_table(engine, table)
            rows = load_table(engine, df, table)
            print(f"  Inserted: {rows:,} rows into {table}")
            success += 1
        except SQLAlchemyError as e:
            print(f"  ERROR: {e}")
            failed.append(table)

        print()

    print(f"=== Done: {success}/{len(TABLES)} tables loaded ===")
    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
