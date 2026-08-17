"""
load_raw.py — Land the ABS API responses in the warehouse, unmodified.

Reads:   data/raw/*.csv   (output of extract.py)
Writes:  SQL Server — schema: raw

This is the only place Python touches the warehouse. It does no cleaning, no
reshaping and no derivation: it lands the ABS response as it arrived, and every
transformation from there is a dbt model under test. That split is the point of
v2 — v1 did its shaping in pandas, where it could not be tested or documented.

The two ABS dataflows have genuinely different dimension sets, so they land in
two tables:

  raw.lf_observations              LF (monthly Labour Force survey)
                                   MEASURE.SEX.AGE.TSEST.REGION.FREQ
  raw.labour_account_observations  ABS_LABOUR_ACCT (annual Labour Account)
                                   MEASURE.ASGS_2016.LABOURACCT_IND.FREQ

Several extracts overlap on the same ABS series (national_summary and
national_fulltime_parttime both request M3 for Persons, seasonally adjusted,
Australia). That duplication is preserved here on purpose and resolved in
stg_labour_force, where a test asserts the overlapping copies agree.

Strategy: DROP and recreate, then bulk INSERT — a full refresh each run. The
whole dataset is ~21k rows, so incremental loading would be complexity without
a payoff.

Requires:
  - pip install -r requirements.txt
  - ODBC Driver 18 for SQL Server
  - a running warehouse:  docker compose up -d

Run: py -3 scripts/load_raw.py
     py -3 scripts/load_raw.py --raw-dir tests/fixtures/raw    (what CI does)
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------------------
# Target tables
# ---------------------------------------------------------------------------

LF_DDL = """
CREATE TABLE raw.lf_observations (
    source_extract  NVARCHAR(50)  NOT NULL,
    dataflow        NVARCHAR(50)  NULL,
    measure         NVARCHAR(10)  NOT NULL,
    sex             NVARCHAR(10)  NOT NULL,
    age             NVARCHAR(10)  NOT NULL,
    tsest           NVARCHAR(10)  NOT NULL,
    region          NVARCHAR(10)  NOT NULL,
    freq            NVARCHAR(5)   NOT NULL,
    time_period     NVARCHAR(10)  NOT NULL,
    obs_value       FLOAT         NULL,
    unit_measure    NVARCHAR(20)  NULL,
    unit_mult       INT           NULL,
    obs_status      NVARCHAR(20)  NULL
)
"""

LABOUR_ACCT_DDL = """
CREATE TABLE raw.labour_account_observations (
    source_extract  NVARCHAR(50)  NOT NULL,
    dataflow        NVARCHAR(50)  NULL,
    measure         NVARCHAR(10)  NOT NULL,
    asgs_2016       NVARCHAR(10)  NOT NULL,
    labouracct_ind  NVARCHAR(20)  NOT NULL,
    freq            NVARCHAR(5)   NOT NULL,
    time_period     NVARCHAR(10)  NOT NULL,
    obs_value       FLOAT         NULL,
    unit_measure    NVARCHAR(20)  NULL,
    unit_mult       INT           NULL,
    obs_status      NVARCHAR(20)  NULL
)
"""

# ABS column name -> warehouse column name. Anything not listed is dropped.
COLUMN_MAP = {
    "DATAFLOW": "dataflow",
    "MEASURE": "measure",
    "SEX": "sex",
    "AGE": "age",
    "TSEST": "tsest",
    "REGION": "region",
    "ASGS_2016": "asgs_2016",
    "LABOURACCT_IND": "labouracct_ind",
    "FREQ": "freq",
    "TIME_PERIOD": "time_period",
    "OBS_VALUE": "obs_value",
    "UNIT_MEASURE": "unit_measure",
    "UNIT_MULT": "unit_mult",
    "OBS_STATUS": "obs_status",
}

# Each target table: the DDL, the columns it accepts, and the extracts landing in it.
TARGETS = {
    "raw.lf_observations": {
        "ddl": LF_DDL,
        "columns": ["source_extract", "dataflow", "measure", "sex", "age", "tsest",
                    "region", "freq", "time_period", "obs_value", "unit_measure",
                    "unit_mult", "obs_status"],
        "extracts": ["national_summary", "national_fulltime_parttime",
                     "state_summary", "national_trend"],
    },
    "raw.labour_account_observations": {
        "ddl": LABOUR_ACCT_DDL,
        "columns": ["source_extract", "dataflow", "measure", "asgs_2016",
                    "labouracct_ind", "freq", "time_period", "obs_value",
                    "unit_measure", "unit_mult", "obs_status"],
        "extracts": ["industry_employment"],
    },
}

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def build_conn_str() -> str:
    """
    The warehouse connection string.

    SQL_CONN_STR wins if set (that is how you point this at Azure SQL or Fabric
    instead). Otherwise it is assembled from the local container's defaults, so
    a clean clone connects with no .env file at all.
    """
    explicit = os.getenv("SQL_CONN_STR")
    if explicit:
        return explicit

    host = os.getenv("MSSQL_HOST", "localhost")
    port = os.getenv("MSSQL_PORT", "1433")
    database = os.getenv("MSSQL_DATABASE", "aus_job_dashboard")
    password = os.getenv("MSSQL_SA_PASSWORD", "LocalDev_Passw0rd!")
    return (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={host},{port};Database={database};Uid=sa;Pwd={password};"
        # The local container presents a self-signed certificate; trusting it is
        # correct here and has no bearing on a cloud target, which uses a real one.
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=60"
    )


def get_engine():
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={build_conn_str()}",
        fast_executemany=True,
    )


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def ensure_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'raw') "
            "EXEC('CREATE SCHEMA raw')"
        ))


def recreate_table(engine, table: str, ddl: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        conn.execute(text(ddl.strip()))


def read_extract(name: str, columns: list[str], raw_dir: Path) -> pd.DataFrame:
    """Read one raw CSV and align it to the target table's columns."""
    path = raw_dir / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run extract.py first.")

    df = pd.read_csv(path, dtype=str)
    df = df.rename(columns=COLUMN_MAP)
    df["source_extract"] = name

    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name}.csv is missing expected columns: {missing}")

    df = df[columns].copy()
    df["obs_value"] = pd.to_numeric(df["obs_value"], errors="coerce")
    df["unit_mult"] = pd.to_numeric(df["unit_mult"], errors="coerce").astype("Int64")
    # NaN is not a valid NVARCHAR value; SQL Server wants a real NULL.
    return df.astype(object).where(pd.notnull(df), None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Land the ABS responses in the warehouse.")
    parser.add_argument(
        "--raw-dir",
        default=str(RAW_DIR),
        help="Directory of ABS CSVs to load. Defaults to data/raw; CI points this "
             "at the committed fixture so its runs do not depend on the ABS API.",
    )
    args = parser.parse_args()
    raw_dir = Path(args.raw_dir)
    if not raw_dir.is_absolute():
        raw_dir = ROOT / raw_dir

    print("=== ABS raw load ===\n")
    print(f"source: {raw_dir}\n")

    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connected to the warehouse.\n")
    except SQLAlchemyError as e:
        print(f"ERROR: could not connect to the warehouse.\n{e}\n")
        print("Is it running?  docker compose up -d")
        sys.exit(1)

    ensure_schema(engine)

    total = 0
    for table, cfg in TARGETS.items():
        print(f"[{table}]")
        frames = []
        for name in cfg["extracts"]:
            df = read_extract(name, cfg["columns"], raw_dir)
            print(f"  {name}: {len(df):,} rows")
            frames.append(df)

        combined = pd.concat(frames, ignore_index=True)
        recreate_table(engine, table, cfg["ddl"])

        schema, tbl = table.split(".")
        combined.to_sql(tbl, engine, schema=schema, if_exists="append",
                        index=False, chunksize=1000)

        print(f"  loaded {len(combined):,} rows\n")
        total += len(combined)

    print(f"=== Done: {total:,} rows landed in schema `raw` ===")


if __name__ == "__main__":
    main()
