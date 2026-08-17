"""
init_warehouse.py — Wait for the warehouse to accept connections, then make sure
the database exists.

`docker compose up -d` already does this locally through its init container, but
CI has no compose file — it gets a bare SQL Server service container with no
database in it. Rather than inline a retry loop into a YAML step, it lives here,
where it is readable and works the same in both places.

Also useful by hand: SQL Server takes 30s+ to accept connections after starting,
and the failure it gives you before then looks identical to a wrong password.

Run: py -3 scripts/init_warehouse.py
     py -3 scripts/init_warehouse.py --timeout 180
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def master_conn_str() -> str:
    """Connection to `master` — the database we are creating does not exist yet."""
    host = os.getenv("MSSQL_HOST", "localhost")
    port = os.getenv("MSSQL_PORT", "1433")
    password = os.getenv("MSSQL_SA_PASSWORD", "LocalDev_Passw0rd!")
    return (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={host},{port};Database=master;Uid=sa;Pwd={password};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=5"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Wait for the warehouse and seed the database.")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Seconds to wait for the server to accept connections.")
    args = parser.parse_args()

    database = os.getenv("MSSQL_DATABASE", "aus_job_dashboard")

    # CREATE DATABASE cannot run inside a transaction, hence autocommit.
    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={master_conn_str()}"
    ).execution_options(isolation_level="AUTOCOMMIT")

    deadline = time.time() + args.timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except SQLAlchemyError as e:
            if time.time() >= deadline:
                print(f"ERROR: warehouse did not accept connections within "
                      f"{args.timeout}s.\n{e}")
                sys.exit(1)
            print(f"  waiting for the warehouse (attempt {attempt}) ...")
            time.sleep(3)

    print(f"Warehouse is accepting connections after {attempt} attempt(s).")

    with engine.connect() as conn:
        conn.execute(text(
            f"IF DB_ID('{database}') IS NULL EXEC('CREATE DATABASE [{database}]')"
        ))
    print(f"Database ready: {database}")


if __name__ == "__main__":
    main()
