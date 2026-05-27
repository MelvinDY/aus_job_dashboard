"""
extract.py — Download ABS Labour Force and Labour Account data via the ABS Data API.

ABS Data API base: https://data.api.abs.gov.au/rest
No API key required.

Dimension key reference (LF dataflow):
  Key format:  MEASURE.SEX.AGE.TSEST.REGION.FREQ
  MEASURE:  M1=Employed FT  M2=Employed PT  M3=Employed total
            M6=Unemployed   M12=Participation rate (%)
            M13=Unemployment rate (%)  M16=Employment-to-pop ratio (%)
  SEX:      1=Male  2=Female  3=Persons
  AGE:      1599=All ages 15+
  TSEST:    10=Original  20=Seasonally adjusted  30=Trend
  REGION:   AUS  1=NSW  2=VIC  3=QLD  4=SA  5=WA  6=TAS  7=NT  8=ACT
  FREQ:     M=Monthly

Dimension key reference (ABS_LABOUR_ACCT dataflow):
  Key format:  MEASURE.ASGS_2016.LABOURACCT_IND.FREQ
  MEASURE:  M9=Employed persons (jobs-based)
  FREQ:     A=Annual

Run: python scripts/extract.py
Output: data/raw/*.csv
"""

import sys
import requests
import pandas as pd
from io import StringIO
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://data.api.abs.gov.au/rest"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

EXTRACTS = {
    # ── LF dataflow (monthly survey) ────────────────────────────────────────
    "national_summary": {
        "description": "National employment, unemployment & rates — SA, persons",
        "dataflow": "LF",
        # Employed total + Unemployed + Participation rate + Unemployment rate + Emp-to-pop ratio
        "key": "M3+M6+M12+M13+M16.3.1599.20.AUS.M",
    },
    "national_fulltime_parttime": {
        "description": "Full-time vs part-time employed by sex — SA",
        "dataflow": "LF",
        # FT + PT + Total, all sexes, SA, Australia
        "key": "M1+M2+M3.1+2+3.1599.20.AUS.M",
    },
    "state_summary": {
        "description": "Employed persons + unemployment rate by state — SA, persons",
        "dataflow": "LF",
        # Employed total + Unemployment rate, persons, all states, SA
        "key": "M3+M13.3.1599.20.1+2+3+4+5+6+7+8.M",
    },
    "national_trend": {
        "description": "National employed and unemployment rate — trend series",
        "dataflow": "LF",
        "key": "M3+M13.3.1599.30.AUS.M",
    },
    # ── ABS_LABOUR_ACCT dataflow (annual, by industry) ──────────────────────
    "industry_employment": {
        "description": "Employed persons by industry — annual, national",
        "dataflow": "ABS_LABOUR_ACCT",
        # Employed persons, Australia, all industry breakdowns, annual
        # Empty middle dimension (..) = all LABOURACCT_IND values
        "key": "M9.AUS..A",
    },
}

# ── Region labels for readability in downstream steps ───────────────────────
REGION_LABELS = {
    "AUS": "Australia",
    "1": "New South Wales",
    "2": "Victoria",
    "3": "Queensland",
    "4": "South Australia",
    "5": "Western Australia",
    "6": "Tasmania",
    "7": "Northern Territory",
    "8": "Australian Capital Territory",
}

# ── Measure labels ───────────────────────────────────────────────────────────
MEASURE_LABELS = {
    "M1": "Employed full-time ('000)",
    "M2": "Employed part-time ('000)",
    "M3": "Employed total ('000)",
    "M6": "Unemployed ('000)",
    "M9": "Employed persons ('000)",
    "M12": "Participation rate (%)",
    "M13": "Unemployment rate (%)",
    "M16": "Employment-to-population ratio (%)",
}

SEX_LABELS = {"1": "Male", "2": "Female", "3": "Persons"}
TSEST_LABELS = {"10": "Original", "20": "Seasonally adjusted", "30": "Trend"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_abs_csv(dataflow: str, key: str, description: str) -> pd.DataFrame:
    url = f"{BASE_URL}/data/{dataflow}/{key}/all"
    print(f"  {description}")
    print(f"  GET {url}")

    try:
        r = requests.get(url, headers={"Accept": "text/csv"}, timeout=60)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"  ERROR HTTP {r.status_code}: {r.text[:200]}")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: {e}")
        return pd.DataFrame()

    if not r.text.strip() or r.text.strip() == "NoRecordsFound":
        print("  WARNING: No records returned.")
        return pd.DataFrame()

    df = pd.read_csv(StringIO(r.text))
    print(f"  {len(df):,} rows downloaded.")
    return df


def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Add human-readable label columns next to dimension code columns."""
    if "MEASURE" in df.columns:
        df.insert(df.columns.get_loc("MEASURE") + 1, "MEASURE_LABEL",
                  df["MEASURE"].map(MEASURE_LABELS).fillna(df["MEASURE"]))
    if "REGION" in df.columns:
        df.insert(df.columns.get_loc("REGION") + 1, "REGION_LABEL",
                  df["REGION"].map(REGION_LABELS).fillna(df["REGION"]))
    if "SEX" in df.columns:
        df.insert(df.columns.get_loc("SEX") + 1, "SEX_LABEL",
                  df["SEX"].map(SEX_LABELS).fillna(df["SEX"]))
    if "TSEST" in df.columns:
        df.insert(df.columns.get_loc("TSEST") + 1, "TSEST_LABEL",
                  df["TSEST"].map(TSEST_LABELS).fillna(df["TSEST"]))
    return df


def save_raw(df: pd.DataFrame, name: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"{name}.csv"
    df.to_csv(out, index=False)
    print(f"  Saved: {out}  ({len(df):,} rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== ABS Labour Force Extract ===\n")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    success, failed = 0, []

    for name, cfg in EXTRACTS.items():
        print(f"[{name}]")
        df = fetch_abs_csv(cfg["dataflow"], cfg["key"], cfg["description"])
        if df.empty:
            failed.append(name)
        else:
            df = add_labels(df)
            save_raw(df, name)
            success += 1
        print()

    print(f"=== Done: {success}/{len(EXTRACTS)} extracts successful ===")
    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
