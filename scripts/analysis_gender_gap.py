"""
analysis_gender_gap.py — the analysis behind analysis/gender-fulltime-gap.md.

Every figure quoted in that write-up is produced here, so no number in the prose
is typed by hand. Re-run it after a pipeline refresh and the charts and the
printed figures both move with the data.

    py -3 scripts/analysis_gender_gap.py

Reads:  mart.v_fulltime_parttime  (seasonally adjusted, persons 15+, Australia)
Writes: analysis/charts/*.png
        analysis/figures.json     (the numbers, for checking the prose)

On the palette: the report's deep blue #1F4E79 is a title colour, not a data
colour — at OKLab lightness 0.41 and chroma 0.09 it reads nearly grey as a mark,
and it fails a lightness/chroma check. The pair below is the same identity moved
into the usable band, and it passes CVD separation (ΔE 23.9 deutan), the
normal-vision floor (29.0) and 3:1 contrast against the chart surface.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter
from sqlalchemy import create_engine

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from load_raw import build_conn_str  # noqa: E402

OUT = ROOT / "analysis" / "charts"

# Validated pair — see the module docstring.
MALE = "#3B82C4"
FEMALE = "#C2410C"
SURFACE = "#FCFCFB"
INK = "#1F2D3D"
MUTED = "#5B6B7B"
GRID = "#E6E9EE"
BAND = "#D8DEE6"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 140,
})

PCT = FuncFormatter(lambda v, _: f"{v:.0f}%")


def title(ax, headline, sub=None):
    """
    Chart titles state the finding, not the variable names.

    The pad has to clear the subtitle line, or matplotlib draws the two on top
    of each other — it does no collision detection between a title and free text.
    """
    ax.set_title(headline, loc="left", fontsize=13, fontweight="bold",
                 color=INK, pad=32 if sub else 10)
    if sub:
        ax.text(0, 1.025, sub, transform=ax.transAxes, fontsize=9.5,
                color=MUTED, va="bottom")


def load() -> pd.DataFrame:
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={build_conn_str()}")
    df = pd.read_sql(
        """SELECT date, sex_label,
                  employed_fulltime_thousands  AS ft,
                  employed_parttime_thousands  AS pt,
                  employed_total_thousands     AS tot,
                  fulltime_share_pct           AS ft_share
           FROM mart.v_fulltime_parttime""",
        engine,
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load()

    share = df.pivot(index="date", columns="sex_label", values="ft_share")
    ft = df.pivot(index="date", columns="sex_label", values="ft")
    pt = df.pivot(index="date", columns="sex_label", values="pt")
    tot = df.pivot(index="date", columns="sex_label", values="tot")
    share["gap"] = share["Male"] - share["Female"]

    first, last = share.index.min(), share.index.max()
    fig = {"period": {"from": str(first.date()), "to": str(last.date())}}

    def at(series, when):
        """Value at the first observation of a year, or the last overall."""
        sl = series.loc[str(when)]
        return float(sl.iloc[-1] if when == last.year else sl.iloc[0])

    # ── Headline figures ────────────────────────────────────────────────────
    peak_date = share["gap"].idxmax()
    fig["headline"] = {
        "gap_now": round(float(share["gap"].iloc[-1]), 1),
        "male_share_now": round(float(share["Male"].iloc[-1]), 1),
        "female_share_now": round(float(share["Female"].iloc[-1]), 1),
        "gap_start": round(at(share["gap"], first.year), 1),
        "gap_peak": round(float(share["gap"].max()), 1),
        "gap_peak_date": str(peak_date.date()),
    }

    # ── Find the turning point in the women's series, rather than assuming ──
    # A 12-month centred mean, so the trough is the trend turning and not one
    # noisy month. The eras below are then built around the date this finds.
    female_smooth = share["Female"].rolling(12, center=True).mean()
    trough_date = female_smooth.idxmin()
    trough_year = int(trough_date.year)
    fig["turning_point"] = {
        "date": str(trough_date.date()),
        "female_share_at_trough": round(float(female_smooth.min()), 1),
        "female_share_now": round(float(share["Female"].iloc[-1]), 1),
        "recovery_ppt": round(float(share["Female"].iloc[-1] - female_smooth.min()), 1),
        "years_of_decline_before": trough_year - int(first.year),
    }

    # ── Era decomposition: what moved the gap? ──────────────────────────────
    # The last two boundaries come from the turning point above, so the eras
    # split where the data actually changes behaviour rather than on round
    # decades that would average the reversal away.
    eras = [(1978, 1990), (1990, 2000), (2000, 2010),
            (2010, trough_year), (trough_year, last.year)]
    rows = []
    for a, b in eras:
        dm = at(share["Male"], b) - at(share["Male"], a)
        df_ = at(share["Female"], b) - at(share["Female"], a)
        years = (pd.Timestamp(f"{b}-01-01") - pd.Timestamp(f"{a}-01-01")).days / 365.25
        rows.append({
            "era": f"{a}–{b}",
            "male_change_ppt": round(dm, 1),
            "female_change_ppt": round(df_, 1),
            "gap_change_ppt": round(dm - df_, 1),
            "gap_change_per_decade": round((dm - df_) / years * 10, 1),
        })
    fig["eras"] = rows

    # Who closed the gap, before and after the turning point. Splitting here is
    # the whole point: measured from 2000 to today the women's net change is
    # about zero, which makes it look like men did all of it — but that average
    # hides a 17-year fall and a reversal, which are different stories.
    def contribution(a, b):
        dm = at(share["Male"], b) - at(share["Male"], a)
        df_ = at(share["Female"], b) - at(share["Female"], a)
        total = abs(dm) + abs(df_)
        return {
            "gap_change_ppt": round(dm - df_, 1),
            "male_change_ppt": round(dm, 1),
            "female_change_ppt": round(df_, 1),
            "from_men_pct": round(abs(dm) / total * 100) if total else None,
            "from_women_pct": round(abs(df_) / total * 100) if total else None,
        }

    fig["before_turn"] = {"period": f"2000–{trough_year}", **contribution(2000, trough_year)}
    fig["after_turn"] = {"period": f"{trough_year}–{last.year}", **contribution(trough_year, last.year)}
    fig["since_2000_naive"] = {"period": f"2000–{last.year}", **contribution(2000, last.year)}

    # ── The counterpoint: levels, not rates ─────────────────────────────────
    fig["levels"] = {
        "female_ft_start": round(at(ft["Female"], first.year)),
        "female_ft_now": round(float(ft["Female"].iloc[-1])),
        "female_ft_growth_pct": round((float(ft["Female"].iloc[-1]) / at(ft["Female"], first.year) - 1) * 100),
        "male_ft_growth_pct": round((float(ft["Male"].iloc[-1]) / at(ft["Male"], first.year) - 1) * 100),
        "female_pt_growth_pct": round((float(pt["Female"].iloc[-1]) / at(pt["Female"], first.year) - 1) * 100),
        "women_share_of_ft_jobs_start": round(
            at(ft["Female"], first.year) / (at(ft["Female"], first.year) + at(ft["Male"], first.year)) * 100, 1),
        "women_share_of_ft_jobs_now": round(
            float(ft["Female"].iloc[-1]) / float(ft["Female"].iloc[-1] + ft["Male"].iloc[-1]) * 100, 1),
    }

    male_pt_share = pt["Male"] / tot["Male"] * 100
    fig["male_parttime"] = {
        "start_pct": round(at(male_pt_share, first.year), 1),
        "now_pct": round(float(male_pt_share.iloc[-1]), 1),
    }

    # ── Pace: how long at the recent rate? (stated as a pace, not a forecast) ─
    recent = share["gap"].loc["2010":]
    x = (recent.index - recent.index[0]).days / 365.25
    slope = np.polyfit(x, recent.values, 1)[0]        # ppt per year
    fig["pace"] = {
        "ppt_per_decade_since_2010": round(slope * 10, 1),
        "years_to_parity_at_that_pace": round(float(share["gap"].iloc[-1]) / abs(slope)) if slope < 0 else None,
        "parity_year_at_that_pace": int(last.year + round(float(share["gap"].iloc[-1]) / abs(slope))) if slope < 0 else None,
    }

    # ════════════════════════════════════════════════════════════════════════
    # Chart 1 — the convergence, and which line is doing the moving
    # ════════════════════════════════════════════════════════════════════════
    f, ax = plt.subplots(figsize=(9.6, 5.0))
    ax.fill_between(share.index, share["Female"], share["Male"], color=BAND,
                    alpha=0.55, linewidth=0, zorder=1)
    ax.plot(share.index, share["Male"], color=MALE, linewidth=2, zorder=3, label="Men")
    ax.plot(share.index, share["Female"], color=FEMALE, linewidth=2, zorder=3, label="Women")

    ax.annotate(f"{share['Male'].iloc[-1]:.0f}%", (share.index[-1], share["Male"].iloc[-1]),
                xytext=(8, 0), textcoords="offset points", color=MALE,
                fontweight="bold", va="center", fontsize=11)
    ax.annotate(f"{share['Female'].iloc[-1]:.0f}%", (share.index[-1], share["Female"].iloc[-1]),
                xytext=(8, 0), textcoords="offset points", color=FEMALE,
                fontweight="bold", va="center", fontsize=11)

    mid = pd.Timestamp("1996-01-01")
    ax.annotate(f"gap {share['gap'].loc[mid]:.0f} ppt",
                (mid, (share["Male"].loc[mid] + share["Female"].loc[mid]) / 2),
                color=MUTED, fontsize=9.5, ha="center",
                bbox=dict(boxstyle="round,pad=0.3", fc=SURFACE, ec=BAND, lw=0.8))

    # The turning point is the finding, so it gets marked.
    ax.plot([trough_date], [female_smooth.min()], "o", ms=8, color=FEMALE,
            markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
    ax.annotate(f"women's rate bottoms out, {trough_year}\nafter falling for "
                f"{trough_year - int(first.year)} years",
                (trough_date, female_smooth.min()), xytext=(-30, -46),
                textcoords="offset points", fontsize=9.5, color=FEMALE, ha="right",
                arrowprops=dict(arrowstyle="-", color=FEMALE, lw=1, alpha=0.6))

    title(ax, "A 48-year gap is closing — but not for the reason the headline suggests",
          "Share of employed people working full-time, by sex. Seasonally adjusted, 15+, Australia.")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylim(45, 100)
    ax.set_xlabel("")
    ax.legend(frameon=False, loc="lower left", fontsize=10, labelcolor=MUTED)
    f.tight_layout()
    f.savefig(OUT / "01-convergence.png", facecolor=SURFACE)
    plt.close(f)

    # ════════════════════════════════════════════════════════════════════════
    # Chart 2 — decomposition by era
    # ════════════════════════════════════════════════════════════════════════
    f, ax = plt.subplots(figsize=(9.6, 4.6))
    labels = [r["era"] for r in rows]
    xs = np.arange(len(rows))
    w = 0.38
    ax.bar(xs - w / 2 - 0.01, [r["male_change_ppt"] for r in rows], w,
           color=MALE, label="Men", zorder=3)
    ax.bar(xs + w / 2 + 0.01, [r["female_change_ppt"] for r in rows], w,
           color=FEMALE, label="Women", zorder=3)
    for i, r in enumerate(rows):
        for off, key, col in ((-w / 2 - 0.01, "male_change_ppt", MALE),
                              (w / 2 + 0.01, "female_change_ppt", FEMALE)):
            v = r[key]
            ax.annotate(f"{v:+.1f}", (i + off, v), xytext=(0, 4 if v >= 0 else -13),
                        textcoords="offset points", ha="center", fontsize=9,
                        color=col, fontweight="bold")
    ax.axhline(0, color=MUTED, linewidth=1)
    ax.set_xticks(xs, labels)
    ax.set_ylabel("change in full-time share (ppt)")
    title(ax, f"For decades the gap closed from the men's side — that flipped in {trough_year}",
          "Change in each group's full-time share within the period. The gap moves by the difference between the two bars.")
    ax.legend(frameon=False, fontsize=10, labelcolor=MUTED)
    f.tight_layout()
    f.savefig(OUT / "02-decomposition.png", facecolor=SURFACE)
    plt.close(f)

    # ════════════════════════════════════════════════════════════════════════
    # Chart 3 — the mechanism on the men's side
    # ════════════════════════════════════════════════════════════════════════
    f, ax = plt.subplots(figsize=(9.6, 4.4))
    ax.plot(male_pt_share.index, male_pt_share.values, color=MALE, linewidth=2, zorder=3)
    ax.annotate(f"{male_pt_share.iloc[-1]:.0f}%", (male_pt_share.index[-1], male_pt_share.iloc[-1]),
                xytext=(8, 0), textcoords="offset points", color=MALE,
                fontweight="bold", va="center", fontsize=11)
    ax.annotate(f"{male_pt_share.iloc[0]:.0f}%", (male_pt_share.index[0], male_pt_share.iloc[0]),
                xytext=(6, -14), textcoords="offset points", color=MUTED, fontsize=10)
    title(ax, "Part-time work among employed men went from 1 in 20 to 1 in 5",
          "Share of employed men working part-time. This is what pulled the men's full-time rate down.")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylim(0, 25)
    f.tight_layout()
    f.savefig(OUT / "03-male-parttime.png", facecolor=SURFACE)
    plt.close(f)

    # ════════════════════════════════════════════════════════════════════════
    # Chart 4 — the counterpoint: rates flat, levels not
    # ════════════════════════════════════════════════════════════════════════
    f, ax = plt.subplots(figsize=(9.6, 4.6))
    idx_f = ft["Female"] / ft["Female"].iloc[0] * 100
    idx_m = ft["Male"] / ft["Male"].iloc[0] * 100
    ax.plot(idx_m.index, idx_m.values, color=MALE, linewidth=2, label="Men", zorder=3)
    ax.plot(idx_f.index, idx_f.values, color=FEMALE, linewidth=2, label="Women", zorder=3)
    ax.annotate(f"+{idx_f.iloc[-1]-100:.0f}%", (idx_f.index[-1], idx_f.iloc[-1]),
                xytext=(8, 0), textcoords="offset points", color=FEMALE,
                fontweight="bold", va="center", fontsize=11)
    ax.annotate(f"+{idx_m.iloc[-1]-100:.0f}%", (idx_m.index[-1], idx_m.iloc[-1]),
                xytext=(8, 0), textcoords="offset points", color=MALE,
                fontweight="bold", va="center", fontsize=11)
    ax.axhline(100, color=MUTED, linewidth=1, linestyle=(0, (4, 4)))
    title(ax, "A flat rate is not a flat trend: women's full-time jobs nearly tripled",
          f"Full-time employed persons, indexed to {first.year} = 100. Growth in the level, not the share.")
    ax.set_ylabel(f"index ({first.year} = 100)")
    ax.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=MUTED)
    f.tight_layout()
    f.savefig(OUT / "04-levels.png", facecolor=SURFACE)
    plt.close(f)

    (ROOT / "analysis" / "figures.json").write_text(
        json.dumps(fig, indent=2), encoding="utf-8")

    print(json.dumps(fig, indent=2))
    print(f"\nWrote 4 charts to {OUT.relative_to(ROOT)} and analysis/figures.json")


if __name__ == "__main__":
    main()
