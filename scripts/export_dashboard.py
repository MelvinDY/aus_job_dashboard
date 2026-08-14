"""Render the four dashboard pages from the mart views to PDF + PNG.

This is a programmatic export of the same four pages defined in the Power BI
report (Overview, State Breakdown, Industry View, Full-time vs Part-time),
pulling the identical dbt-built mart views the .pbip consumes. It produces:

    powerbi/dashboard_export.pdf   - 4-page dashboard (portfolio deliverable)
    powerbi/dashboard_overview.png - Overview page, for the README screenshot

These are matplotlib renders, not screenshots of the Power BI report — they
exist so the repo shows the numbers without needing Power BI Desktop installed.

Run after the pipeline:  py -3 scripts/export_dashboard.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from dotenv import load_dotenv
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parent.parent
OUT_PDF = ROOT / "powerbi" / "dashboard_export.pdf"
OUT_PNG = ROOT / "powerbi" / "dashboard_overview.png"

NAVY = "#1f3a5f"
BLUE = "#2e6da4"
TEAL = "#3aa8a0"
AMBER = "#e0922f"
RED = "#c0392b"
GREEN = "#2e8b57"
GREY = "#8a94a6"
BG = "#f5f7fa"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": "#cdd4df",
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "grid.color": "#e3e8ef",
    "grid.linewidth": 0.7,
    "axes.axisbelow": True,
})


def get_engine():
    load_dotenv(ROOT / ".env")
    # One definition of how to reach the warehouse, shared with the loader:
    # local container by default, any SQL Server target via SQL_CONN_STR.
    sys.path.insert(0, str(ROOT / "scripts"))
    from load_raw import build_conn_str

    conn_str = build_conn_str()
    if "timeout" not in conn_str.lower():
        conn_str = conn_str.rstrip(";") + ";Connection Timeout=120"
    return create_engine(f"mssql+pyodbc:///?odbc_connect={conn_str}")


def page_header(fig, title, subtitle):
    fig.patch.set_facecolor("white")
    fig.text(0.04, 0.955, title, fontsize=20, fontweight="bold", color=NAVY)
    fig.text(0.04, 0.925, subtitle, fontsize=10.5, color=GREY)
    fig.text(0.96, 0.955, "Australian Labour Market Analytics", fontsize=9,
             color=GREY, ha="right")


def kpi_card(ax, label, value, delta=None, delta_good_down=False):
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                               facecolor=BG, edgecolor="#dfe5ee", lw=1))
    ax.text(0.5, 0.66, value, ha="center", va="center", fontsize=26,
            fontweight="bold", color=NAVY, transform=ax.transAxes)
    ax.text(0.5, 0.28, label, ha="center", va="center", fontsize=11,
            color="#55617a", transform=ax.transAxes)
    if delta is not None:
        up = delta >= 0
        good = (not up) if delta_good_down else up
        color = GREEN if good else RED
        arrow = "▲" if up else "▼"
        ax.text(0.5, 0.07, f"{arrow} {abs(delta):.2f} vs prev. month",
                ha="center", va="center", fontsize=8.5, color=color,
                transform=ax.transAxes)


def overview_page(pdf, eng):
    df = pd.read_sql("SELECT * FROM mart.v_national_overview ORDER BY date", eng,
                     parse_dates=["date"])
    latest = df.iloc[-1]
    recent = df[df["date"] >= df["date"].max() - pd.DateOffset(years=15)]

    fig = plt.figure(figsize=(11.69, 8.27))  # A4 landscape
    page_header(fig, "Overview",
                f"National labour market — latest: {latest['date']:%B %Y}")
    gs = fig.add_gridspec(2, 3, left=0.06, right=0.95, top=0.86, bottom=0.08,
                          hspace=0.35, wspace=0.22, height_ratios=[0.8, 2])

    kpi_card(fig.add_subplot(gs[0, 0]), "Employed persons",
             f"{latest['employed_thousands']/1000:,.2f}M",
             delta=latest.get("employed_mom_change_pct"))
    kpi_card(fig.add_subplot(gs[0, 1]), "Unemployment rate",
             f"{latest['unemployment_rate_pct']:.1f}%",
             delta=latest.get("unemployment_rate_mom_change_ppt"),
             delta_good_down=True)
    kpi_card(fig.add_subplot(gs[0, 2]), "Participation rate",
             f"{latest['participation_rate_pct']:.1f}%")

    ax = fig.add_subplot(gs[1, :])
    ax.plot(recent["date"], recent["unemployment_rate_pct"], color=BLUE, lw=2)
    ax.fill_between(recent["date"], recent["unemployment_rate_pct"],
                    recent["unemployment_rate_pct"].min() - 0.3,
                    color=BLUE, alpha=0.08)
    ax.set_title("National unemployment rate (last 15 years)", fontsize=12,
                 color=NAVY, loc="left", pad=10)
    ax.set_ylabel("Unemployment rate (%)")
    ax.margins(x=0.01)
    fig.savefig(OUT_PNG, dpi=130, facecolor="white", bbox_inches="tight")
    pdf.savefig(fig, facecolor="white")
    plt.close(fig)


def state_page(pdf, eng):
    df = pd.read_sql(
        "SELECT * FROM mart.v_unemployment_by_state WHERE is_latest_month = 1", eng,
        parse_dates=["date"])
    df = df.sort_values("unemployment_rate_pct")
    when = df["date"].iloc[0] if len(df) else None

    fig = plt.figure(figsize=(11.69, 8.27))
    page_header(fig, "State Breakdown",
                f"Unemployment rate & employed persons by state — {when:%B %Y}")
    gs = fig.add_gridspec(1, 2, left=0.14, right=0.96, top=0.86, bottom=0.10,
                          wspace=0.55)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.barh(df["region_name"], df["unemployment_rate_pct"], color=BLUE)
    for y, v in enumerate(df["unemployment_rate_pct"]):
        ax1.text(v + 0.05, y, f"{v:.1f}%", va="center", fontsize=9, color=NAVY)
    ax1.set_title("Unemployment rate by state", fontsize=12, color=NAVY,
                  loc="left", pad=10)
    ax1.set_xlabel("Unemployment rate (%)")
    ax1.grid(axis="y", visible=False)

    df2 = df.sort_values("employed_thousands")
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.barh(df2["region_name"], df2["employed_thousands"] / 1000, color=TEAL)
    for y, v in enumerate(df2["employed_thousands"] / 1000):
        ax2.text(v + 0.02, y, f"{v:,.2f}M", va="center", fontsize=9, color=NAVY)
    ax2.set_title("Employed persons by state", fontsize=12, color=NAVY,
                  loc="left", pad=10)
    ax2.set_xlabel("Employed persons (millions)")
    ax2.grid(axis="y", visible=False)

    pdf.savefig(fig, facecolor="white")
    plt.close(fig)


def industry_page(pdf, eng):
    df = pd.read_sql(
        "SELECT * FROM mart.v_industry_breakdown WHERE is_latest_year = 1", eng,
        parse_dates=["date"])
    df = df.sort_values("employed_yoy_change_pct")
    when = df["date"].iloc[0] if len(df) else None
    cmap = {"Growing": GREEN, "Shrinking": RED, "Stable": GREY}
    colors = df["growth_category"].map(cmap).fillna(GREY)

    fig = plt.figure(figsize=(11.69, 8.27))
    page_header(fig, "Industry View",
                f"Employment growth by industry (YoY) — {when:%Y}")
    ax = fig.add_axes([0.30, 0.10, 0.64, 0.76])
    ax.barh(df["industry_name"], df["employed_yoy_change_pct"], color=colors)
    ax.axvline(0, color="#9aa3b2", lw=1)
    for y, v in enumerate(df["employed_yoy_change_pct"]):
        ax.text(v + (0.1 if v >= 0 else -0.1), y, f"{v:+.1f}%",
                va="center", ha="left" if v >= 0 else "right",
                fontsize=8.5, color=NAVY)
    ax.set_title("Year-on-year employment change by industry", fontsize=12,
                 color=NAVY, loc="left", pad=10)
    ax.set_xlabel("YoY change in employed persons (%)")
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in cmap.values()]
    ax.legend(handles, cmap.keys(), loc="lower right", frameon=False,
              fontsize=9, title="Growth category")
    pdf.savefig(fig, facecolor="white")
    plt.close(fig)


def fulltime_parttime_page(pdf, eng):
    df = pd.read_sql("SELECT * FROM mart.v_fulltime_parttime ORDER BY date", eng,
                     parse_dates=["date"])
    recent = df[df["date"] >= df["date"].max() - pd.DateOffset(years=15)]

    fig = plt.figure(figsize=(11.69, 8.27))
    page_header(fig, "Full-time vs Part-time",
                "Employment type over time, split by gender (last 15 years)")
    gs = fig.add_gridspec(1, 2, left=0.07, right=0.96, top=0.86, bottom=0.10,
                          wspace=0.22)

    for ax, sex, title in [(fig.add_subplot(gs[0, 0]), "Male", "Male"),
                           (fig.add_subplot(gs[0, 1]), "Female", "Female")]:
        s = recent[recent["sex_label"] == sex].sort_values("date")
        ax.stackplot(s["date"],
                     s["employed_fulltime_thousands"] / 1000,
                     s["employed_parttime_thousands"] / 1000,
                     labels=["Full-time", "Part-time"],
                     colors=[NAVY, AMBER], alpha=0.9)
        ax.set_title(title, fontsize=12, color=NAVY, loc="left", pad=10)
        ax.set_ylabel("Employed persons (millions)")
        ax.margins(x=0.01)
        ax.legend(loc="upper left", frameon=False, fontsize=9)

    pdf.savefig(fig, facecolor="white")
    plt.close(fig)


def main():
    eng = get_engine()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUT_PDF) as pdf:
        overview_page(pdf, eng)
        state_page(pdf, eng)
        industry_page(pdf, eng)
        fulltime_parttime_page(pdf, eng)
        meta = pdf.infodict()
        meta["Title"] = "Australian Labour Market Analytics Dashboard"
        meta["Author"] = "Melvin Darial Yogiana"
    print(f"Wrote {OUT_PDF.relative_to(ROOT)}")
    print(f"Wrote {OUT_PNG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
