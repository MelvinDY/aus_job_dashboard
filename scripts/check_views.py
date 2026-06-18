import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
conn_str = os.getenv("AZURE_SQL_CONN_STR")
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={conn_str}")

with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.VIEWS
        WHERE TABLE_SCHEMA IN ('staging', 'mart')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)).fetchall()

print(f"Found {len(rows)} views:")
for r in rows:
    print(f"  {r[0]}.{r[1]}")
