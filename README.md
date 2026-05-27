# Australian Labour Market Analytics Dashboard

An end-to-end data analytics project using real ABS Labour Force data — from raw government
CSVs through to a Power BI dashboard via Azure SQL.

**Stack:** Python · Pandas · Azure SQL · SQL Views · Power BI · GitHub

---

## Pipeline

```
ABS CSV  →  Python (Pandas)  →  Azure SQL (staging → mart)  →  Power BI
```

1. Download ABS Labour Force survey data (no API key needed)
2. Clean & reshape with Pandas, load into Azure SQL
3. Transform with SQL views (staging → mart pattern)
4. Connect Power BI to mart views, build 4 report pages

## Dashboard Pages

- **Overview** — National unemployment trend, employed persons, participation rate
- **State Breakdown** — Map + bar chart across all Australian states
- **Industry View** — Sector growth/decline (tech, healthcare, retail, construction)
- **Full-time vs Part-time** — Employment type trend split by gender

## Setup

1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your Azure SQL connection string
4. Run `python scripts/extract.py` → `python scripts/transform.py` → `python scripts/load.py`
5. Open Power BI Desktop and connect to your Azure SQL mart views

## Portfolio

- Data portfolio: melvindy.vercel.app/projects/data
