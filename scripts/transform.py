"""
transform.py — Clean and reshape ABS raw data for the Azure SQL load step.

Reads:   data/raw/*.csv   (output of extract.py)
Writes:  data/processed/*.csv

Transformations applied to every file:
  - TIME_PERIOD parsed to a proper date column
  - Numeric dimension codes mapped to human-readable labels
  - Metadata columns dropped (DATAFLOW, AGE, UNIT_MEASURE, etc.)
  - OBS_VALUE coerced to float; rows with null values dropped

File-specific transforms:
  - national_summary        → wide pivot: one column per measure
  - state_summary           → adds full state names
  - fulltime_parttime       → adds FT/PT share columns (% of total employed)
  - national_trend          → same cleaning, kept long format
  - industry_employment     → filtered to ANZSIC division level; adds YoY growth %

Run: python scripts/transform.py
"""

import sys
import pandas as pd
from pathlib import Path

RAW_DIR       = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

REGION_LABELS = {
    "AUS": "Australia",
    "1":   "New South Wales",
    "2":   "Victoria",
    "3":   "Queensland",
    "4":   "South Australia",
    "5":   "Western Australia",
    "6":   "Tasmania",
    "7":   "Northern Territory",
    "8":   "Australian Capital Territory",
}

SEX_LABELS   = {"1": "Male", "2": "Female", "3": "Persons"}
TSEST_LABELS = {"10": "Original", "20": "Seasonally adjusted", "30": "Trend"}

# ANZSIC 2006 division names (single-letter codes = division level)
INDUSTRY_LABELS = {
    "A":     "Agriculture, Forestry & Fishing",
    "B":     "Mining",
    "C":     "Manufacturing",
    "D":     "Electricity, Gas, Water & Waste",
    "E":     "Construction",
    "F":     "Wholesale Trade",
    "G":     "Retail Trade",
    "H":     "Accommodation & Food Services",
    "I":     "Transport, Postal & Warehousing",
    "J":     "Information Media & Telecommunications",
    "K":     "Financial & Insurance Services",
    "L":     "Rental, Hiring & Real Estate",
    "M":     "Professional, Scientific & Technical",
    "N":     "Administrative & Support Services",
    "O":     "Public Administration & Safety",
    "P":     "Education & Training",
    "Q":     "Health Care & Social Assistance",
    "R":     "Arts & Recreation Services",
    "S":     "Other Services",
    "TOTAL": "All Industries",
}

# Columns to drop from every output — they add no analytical value
METADATA_COLS = [
    "DATAFLOW", "AGE", "FREQ", "UNIT_MEASURE", "UNIT_MULT",
    "OBS_STATUS", "OBS_COMMENT", "DECIMALS",
]

# Short column names used after pivoting national_summary
MEASURE_SHORT = {
    "M3":  "employed_thousands",
    "M6":  "unemployed_thousands",
    "M12": "participation_rate_pct",
    "M13": "unemployment_rate_pct",
    "M16": "emp_to_pop_ratio_pct",
}

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def parse_period(series: pd.Series) -> pd.Series:
    """
    Convert TIME_PERIOD strings to proper dates.
      '1978-02'  → 1978-02-01  (monthly LF data)
      '1995'     → 1995-01-01  (annual Labour Account)
    """
    def _parse(val):
        val = str(val).strip()
        if len(val) == 4:           # annual: "1995"
            return pd.Timestamp(f"{val}-01-01")
        return pd.Timestamp(val + "-01")   # monthly: "1978-02"

    return series.map(_parse)


def fix_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Re-apply all dimension label columns after type-safe conversion."""
    if "REGION" in df.columns:
        df["REGION_LABEL"] = df["REGION"].astype(str).map(REGION_LABELS).fillna(df["REGION"].astype(str))
    if "SEX" in df.columns:
        df["SEX_LABEL"] = df["SEX"].astype(str).map(SEX_LABELS).fillna(df["SEX"].astype(str))
    if "TSEST" in df.columns:
        df["TSEST_LABEL"] = df["TSEST"].astype(str).map(TSEST_LABELS).fillna(df["TSEST"].astype(str))
    if "MEASURE" in df.columns:
        measure_labels = {
            "M1":  "Employed full-time ('000)",
            "M2":  "Employed part-time ('000)",
            "M3":  "Employed total ('000)",
            "M6":  "Unemployed ('000)",
            "M9":  "Employed persons ('000)",
            "M12": "Participation rate (%)",
            "M13": "Unemployment rate (%)",
            "M16": "Employment-to-population ratio (%)",
        }
        df["MEASURE_LABEL"] = df["MEASURE"].map(measure_labels).fillna(df["MEASURE"])
    return df


def base_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates, fix labels, coerce values, drop metadata."""
    df = df.copy()
    df["date"] = parse_period(df["TIME_PERIOD"])
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE"])
    df = fix_labels(df)
    drop = [c for c in METADATA_COLS if c in df.columns]
    df = df.drop(columns=drop + ["TIME_PERIOD"])
    return df


def save(df: pd.DataFrame, name: str) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / f"{name}.csv"
    df.to_csv(out, index=False)
    print(f"  Saved: {out}  ({len(df):,} rows, {df.shape[1]} cols)")


# ---------------------------------------------------------------------------
# Per-file transforms
# ---------------------------------------------------------------------------

def transform_national_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot so each row is one month and each measure is a column.
    Output columns: date, employed_thousands, unemployed_thousands,
                    participation_rate_pct, unemployment_rate_pct, emp_to_pop_ratio_pct
    """
    df = base_clean(df)
    pivot = (
        df.pivot_table(index="date", columns="MEASURE", values="OBS_VALUE", aggfunc="first")
          .reset_index()
    )
    pivot.columns.name = None
    pivot = pivot.rename(columns=MEASURE_SHORT)
    # Keep only expected columns (drops any unexpected measures gracefully)
    keep = ["date"] + [v for v in MEASURE_SHORT.values() if v in pivot.columns]
    pivot = pivot[keep].sort_values("date")
    return pivot


def transform_state_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot so each row is one state × month, with columns for employed and unemployment rate.
    """
    df = base_clean(df)
    pivot = (
        df.pivot_table(index=["date", "REGION", "REGION_LABEL"], columns="MEASURE",
                       values="OBS_VALUE", aggfunc="first")
          .reset_index()
    )
    pivot.columns.name = None
    rename = {"M3": "employed_thousands", "M13": "unemployment_rate_pct"}
    pivot = pivot.rename(columns=rename)
    keep_cols = ["date", "REGION", "REGION_LABEL"] + [v for v in rename.values() if v in pivot.columns]
    return pivot[keep_cols].sort_values(["REGION_LABEL", "date"])


def transform_fulltime_parttime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot to wide format by sex (Male/Female/Persons) × employment type (FT/PT/Total).
    Adds FT share and PT share columns for Persons.
    """
    df = base_clean(df)
    pivot = (
        df.pivot_table(index=["date", "SEX", "SEX_LABEL"], columns="MEASURE",
                       values="OBS_VALUE", aggfunc="first")
          .reset_index()
    )
    pivot.columns.name = None
    rename = {
        "M1": "employed_fulltime_thousands",
        "M2": "employed_parttime_thousands",
        "M3": "employed_total_thousands",
    }
    pivot = pivot.rename(columns=rename)

    # Add FT/PT share % for each sex group
    if {"employed_fulltime_thousands", "employed_total_thousands"}.issubset(pivot.columns):
        pivot["fulltime_share_pct"] = (
            pivot["employed_fulltime_thousands"] / pivot["employed_total_thousands"] * 100
        ).round(2)
        pivot["parttime_share_pct"] = (
            pivot["employed_parttime_thousands"] / pivot["employed_total_thousands"] * 100
        ).round(2)

    keep = ["date", "SEX", "SEX_LABEL"] + [
        c for c in [
            "employed_fulltime_thousands", "employed_parttime_thousands",
            "employed_total_thousands", "fulltime_share_pct", "parttime_share_pct",
        ] if c in pivot.columns
    ]
    return pivot[keep].sort_values(["SEX_LABEL", "date"])


def transform_national_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Keep long format — just clean and relabel."""
    df = base_clean(df)
    rename = {"M3": "Employed total ('000)", "M13": "Unemployment rate (%)"}
    df["MEASURE_LABEL"] = df["MEASURE"].map(rename).fillna(df["MEASURE"])
    keep = ["date", "MEASURE", "MEASURE_LABEL", "OBS_VALUE"]
    return df[[c for c in keep if c in df.columns]].sort_values(["MEASURE", "date"])


def transform_industry_employment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter to ANZSIC division level (single-letter codes + TOTAL).
    Add industry name, calculate YoY employed persons change.
    """
    df = df.copy()
    df["date"] = parse_period(df["TIME_PERIOD"])
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE"])

    # Keep only division-level codes
    division_codes = set(INDUSTRY_LABELS.keys())
    df = df[df["LABOURACCT_IND"].isin(division_codes)].copy()

    df["industry_name"] = df["LABOURACCT_IND"].map(INDUSTRY_LABELS)
    df = df.rename(columns={
        "LABOURACCT_IND": "industry_code",
        "OBS_VALUE":      "employed_thousands",
    })

    # YoY absolute and percentage change
    df = df.sort_values(["industry_code", "date"])
    df["employed_yoy_change_thousands"] = df.groupby("industry_code")["employed_thousands"].diff(1).round(3)
    df["employed_yoy_change_pct"] = (
        df["employed_yoy_change_thousands"] / df.groupby("industry_code")["employed_thousands"].shift(1) * 100
    ).round(2)

    drop = [c for c in METADATA_COLS + ["TIME_PERIOD", "ASGS_2016", "MEASURE", "MEASURE_LABEL"] if c in df.columns]
    df = df.drop(columns=drop)

    keep = ["date", "industry_code", "industry_name", "employed_thousands",
            "employed_yoy_change_thousands", "employed_yoy_change_pct"]
    return df[[c for c in keep if c in df.columns]].sort_values(["industry_name", "date"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TRANSFORMS = {
    "national_summary":        transform_national_summary,
    "state_summary":           transform_state_summary,
    "national_fulltime_parttime": transform_fulltime_parttime,
    "national_trend":          transform_national_trend,
    "industry_employment":     transform_industry_employment,
}

def main() -> None:
    print("=== ABS Labour Force Transform ===\n")
    success, failed = 0, []

    for name, fn in TRANSFORMS.items():
        print(f"[{name}]")
        raw_path = RAW_DIR / f"{name}.csv"
        if not raw_path.exists():
            print(f"  SKIP: {raw_path} not found — run extract.py first.")
            failed.append(name)
            print()
            continue

        df_raw = pd.read_csv(raw_path)
        print(f"  Raw: {len(df_raw):,} rows")

        df_clean = fn(df_raw)
        save(df_clean, name)
        success += 1
        print()

    print(f"=== Done: {success}/{len(TRANSFORMS)} transforms successful ===")
    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
