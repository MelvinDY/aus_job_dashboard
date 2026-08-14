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
        "description": "Employed persons + unemployment rate by state — Trend, persons",
        "dataflow": "LF",
        # Employed total + Unemployment rate, persons, all 8 states/territories.
        #
        # TSEST=30 (Trend), NOT 20 (Seasonally adjusted): the ABS does not publish
        # a seasonally adjusted series for NT (7) or ACT (8) — those keys 404,
        # because the territory samples are too small to seasonally adjust.
        # Asking for SA across 1..8 silently returned only the 6 states that have
        # it, which is how ACT and NT went missing from the dashboard.
        # Trend exists for all 8, so every jurisdiction sits on ONE comparable
        # basis — required, since this page ranks states against each other.
        "key": "M3+M13.3.1599.30.1+2+3+4+5+6+7+8.M",
        "expect": {"REGION": 8},
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

# Dimension codes are NOT decoded here. The raw layer stays a faithful copy of
# the ABS response, and every code -> label mapping lives in a dbt seed feeding
# dim_series, where it is version-controlled and covered by accepted_values
# tests. (v1 decoded labels at this step and got them silently wrong: the maps
# were keyed by string while the CSV parsed the codes as integers, so every
# SEX_LABEL came out as "3" rather than "Persons".)

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


def validate(df: pd.DataFrame, name: str, expect: dict[str, int]) -> list[str]:
    """
    Assert that each dimension came back with the number of members we expect.

    The ABS API does not error when you ask for dimension members that don't
    exist — it just returns the ones that do. A key requesting all 8 states can
    quietly come back with 6, and every downstream chart will render a
    well-formed picture of an incomplete country. Row counts don't catch this;
    only counting distinct members does.
    """
    problems = []
    for col, want in expect.items():
        got = df[col].nunique()
        if got != want:
            members = sorted(df[col].unique().tolist())
            problems.append(
                f"{name}: expected {want} distinct {col} values, got {got} -> {members}"
            )
    return problems


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

    success, failed, incomplete = 0, [], []

    for name, cfg in EXTRACTS.items():
        print(f"[{name}]")
        df = fetch_abs_csv(cfg["dataflow"], cfg["key"], cfg["description"])
        if df.empty:
            failed.append(name)
        else:
            problems = validate(df, name, cfg.get("expect", {}))
            for p in problems:
                print(f"  INCOMPLETE: {p}")
            incomplete.extend(problems)

            save_raw(df, name)
            success += 1
        print()

    print(f"=== Done: {success}/{len(EXTRACTS)} extracts successful ===")
    if incomplete:
        print("\nDIMENSION COMPLETENESS FAILURES:")
        for p in incomplete:
            print(f"  - {p}")
    if failed:
        print(f"Failed: {failed}")
    if failed or incomplete:
        sys.exit(1)


if __name__ == "__main__":
    main()
