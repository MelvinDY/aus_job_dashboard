"""
run_pipeline.py — the whole pipeline, one command.

    py -3 run_pipeline.py                  extract -> load -> dbt build -> export
    py -3 run_pipeline.py --skip-extract   rebuild from the raw files already on disk
    py -3 run_pipeline.py --full-refresh   force dbt to rebuild seeds and tables

Prerequisite: a running warehouse.

    docker compose up -d

That is the whole setup. No cloud account, no API key, no secrets — the ABS
Data API is open, and the warehouse is a local container with a development
password that is published in .env.example on purpose.

STEPS
  1. extract      ABS Data API           -> data/raw/*.csv
  2. load raw     data/raw/*.csv         -> schema `raw`
  3. dbt build    raw -> staging -> star -> mart, running every test as it goes
  4. export       mart                   -> excel/data/*.csv for the workbook

Step 3 is the one that matters: `dbt build` interleaves models and tests, so a
model whose test fails does not get used by anything downstream. A bad extract
stops here rather than reaching the report.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DBT_DIR = ROOT / "dbt"


def dbt_executable() -> str:
    """
    dbt ships as a console script next to the interpreter running this file.

    Resolved from sys.executable rather than PATH: pip installs it into a
    Scripts directory that is frequently not on PATH on Windows, and `python -m
    dbt` does not work because dbt is a package with no __main__.
    """
    scripts = Path(sys.executable).parent / ("Scripts" if os.name == "nt" else "bin")
    exe = scripts / ("dbt.exe" if os.name == "nt" else "dbt")
    return str(exe) if exe.exists() else "dbt"


def run(label: str, cmd: list[str], cwd: Path = ROOT, env: dict = None) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(f"$ {' '.join(str(c) for c in cmd)}\n")
    started = time.time()
    result = subprocess.run(cmd, cwd=str(cwd), env=env)
    if result.returncode != 0:
        print(f"\nFAILED: {label} (exit {result.returncode})")
        sys.exit(result.returncode)
    print(f"\n  {label} finished in {time.time() - started:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Australian labour market warehouse end to end.",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Reuse the ABS files already in data/raw instead of calling the API.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Pass --full-refresh to dbt, rebuilding seeds and tables from scratch.",
    )
    args = parser.parse_args()

    py = sys.executable

    # 1 ── Extract ────────────────────────────────────────────────────────────
    if args.skip_extract:
        print("Skipping extract — using the existing files in data/raw.")
    else:
        run("1/4  Extract — ABS Data API to data/raw",
            [py, str(ROOT / "scripts" / "extract.py")])

    # 2 ── Load raw ───────────────────────────────────────────────────────────
    run("2/4  Load — data/raw to schema `raw`",
        [py, str(ROOT / "scripts" / "load_raw.py")])

    # 3 ── dbt build ──────────────────────────────────────────────────────────
    # profiles.yml is checked into dbt/, so point dbt at it rather than relying
    # on a ~/.dbt directory the person cloning this repo has never created.
    dbt_env = {**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)}
    dbt = dbt_executable()

    run("3/4  dbt deps — install packages",
        [dbt, "deps"], cwd=DBT_DIR, env=dbt_env)

    build_cmd = [dbt, "build"]
    if args.full_refresh:
        build_cmd.append("--full-refresh")
    run("3/4  dbt build — models and tests, raw to mart",
        build_cmd, cwd=DBT_DIR, env=dbt_env)

    # 4 ── Export for Excel ───────────────────────────────────────────────────
    run("4/4  Export — mart to excel/data for the workbook",
        [py, str(ROOT / "scripts" / "export_mart.py")])

    print(f"\n{'=' * 70}")
    print("Pipeline complete.")
    print(f"{'=' * 70}")
    print("  Warehouse : mart.v_national_overview, v_unemployment_by_state,")
    print("              v_industry_breakdown, v_fulltime_parttime")
    print("  Excel     : excel/data/*.csv  (refresh the workbook to pick these up)")
    print("  Power BI  : powerbi/aus_job_dashboard.pbip  (open and Refresh)")
    print("  dbt docs  : cd dbt && dbt docs generate && dbt docs serve")


if __name__ == "__main__":
    main()
