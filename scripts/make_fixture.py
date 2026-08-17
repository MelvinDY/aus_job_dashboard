"""
make_fixture.py — Build the committed CI fixture from data/raw.

CI needs raw input that does not depend on the ABS API being up. A portfolio
repo whose build badge goes red because a government website had an outage is
worse than no badge, so pull-request runs load this fixture instead of calling
the API. (A separate scheduled workflow still runs the live extract — that one
is meant to fail loudly when the ABS changes something.)

The fixture is a date-trimmed copy of a real extract, not synthetic data. Every
property the tests assert has to survive the trim:

  - all 8 jurisdictions, in every month     (assert_all_jurisdictions_present)
  - one adjustment basis per comparison     (assert_no_mixed_adjustment_types)
  - the deliberately overlapping series      (assert_overlapping_extracts_agree)
  - >= 13 months, so the 12-month lag in every year-on-year column resolves
  - >= 2 years of the annual Labour Account, for its year-on-year column

Monthly series are cut to FIXTURE_FROM_YEAR; the annual industry file is kept
whole because it is small and its year-on-year lag needs the history.

Run: py -3 scripts/make_fixture.py
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "raw"

# Monthly files are trimmed to this year onward. Far more than the 13 months the
# lags need — enough that a chart built from the fixture still looks like a
# trend, which makes the fixture usable for debugging, not just for CI.
FIXTURE_FROM_YEAR = 2015

MONTHLY = ["national_summary", "national_fulltime_parttime", "state_summary", "national_trend"]
ANNUAL = ["industry_employment"]


def main() -> None:
    if not RAW_DIR.exists():
        sys.exit(f"ERROR: {RAW_DIR} not found — run: py -3 scripts/extract.py")

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    total = 0

    for name in MONTHLY:
        src = RAW_DIR / f"{name}.csv"
        if not src.exists():
            sys.exit(f"ERROR: {src} not found — run: py -3 scripts/extract.py")

        df = pd.read_csv(src, dtype=str)
        year = df["TIME_PERIOD"].str.slice(0, 4).astype(int)
        trimmed = df[year >= FIXTURE_FROM_YEAR].copy()

        out = FIXTURE_DIR / f"{name}.csv"
        trimmed.to_csv(out, index=False)
        print(f"  {name:<28} {len(df):>7,} -> {len(trimmed):>6,} rows"
              f"  ({trimmed['TIME_PERIOD'].min()} to {trimmed['TIME_PERIOD'].max()})")
        total += len(trimmed)

    for name in ANNUAL:
        src = RAW_DIR / f"{name}.csv"
        df = pd.read_csv(src, dtype=str)
        out = FIXTURE_DIR / f"{name}.csv"
        df.to_csv(out, index=False)
        print(f"  {name:<28} {len(df):>7,} -> {len(df):>6,} rows  (kept whole)")
        total += len(df)

    # Guard the property the trim is most likely to break.
    state = pd.read_csv(FIXTURE_DIR / "state_summary.csv", dtype=str)
    regions = state["REGION"].nunique()
    if regions != 8:
        sys.exit(f"ERROR: fixture has {regions} jurisdictions, expected 8 — "
                 "CI's assert_all_jurisdictions_present would fail.")

    print(f"\n  all 8 jurisdictions present")
    print(f"=== Fixture written to tests/fixtures/raw ({total:,} rows) ===")


if __name__ == "__main__":
    main()
