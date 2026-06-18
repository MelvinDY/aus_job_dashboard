"""Deploy all SQL views to Azure SQL via SQLAlchemy."""
import os, re
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
conn_str = os.getenv("AZURE_SQL_CONN_STR")
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={conn_str}")

STATEMENTS = [
    # Schemas
    "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'staging') EXEC('CREATE SCHEMA staging')",
    "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'mart')    EXEC('CREATE SCHEMA mart')",
    # Views in dependency order (staging first, then mart)
]

VIEW_FILES = [
    "sql/staging/v_national_summary.sql",
    "sql/staging/v_state_summary.sql",
    "sql/staging/v_fulltime_parttime.sql",
    "sql/staging/v_industry_employment.sql",
    "sql/mart/v_national_overview.sql",
    "sql/mart/v_unemployment_by_state.sql",
    "sql/mart/v_industry_breakdown.sql",
    "sql/mart/v_fulltime_parttime.sql",
]

BASE = Path(__file__).resolve().parent.parent

for f in VIEW_FILES:
    sql = (BASE / f).read_text(encoding="utf-8")
    # Strip GO statements and comments, keep CREATE OR ALTER VIEW block
    sql = re.sub(r'--[^\n]*', '', sql)   # remove line comments
    sql = re.sub(r'\bGO\b', '', sql, flags=re.IGNORECASE).strip()
    STATEMENTS.append(sql)

with engine.begin() as conn:
    for i, stmt in enumerate(STATEMENTS):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            conn.execute(text(stmt))
            label = VIEW_FILES[i - 2] if i >= 2 else f"statement {i+1}"
            print(f"  OK: {label}")
        except Exception as e:
            label = VIEW_FILES[i - 2] if i >= 2 else f"statement {i+1}"
            print(f"  ERROR [{label}]: {e}")

print("\nDone. Verifying...")
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS "
        "WHERE TABLE_SCHEMA IN ('staging','mart') ORDER BY TABLE_SCHEMA, TABLE_NAME"
    )).fetchall()
    print(f"Views in database ({len(rows)}):")
    for r in rows:
        print(f"  {r[0]}.{r[1]}")
