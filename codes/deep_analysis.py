"""
Day 4: Deeper Analysis - understanding WHY the CPI moved the way it did.

Focuses on Transport and Food (the two biggest drivers from Day 3),
plus flags the single most extreme month-over-month swings across
all categories - these are your "what happened here?" investigation points.

Usage:
    python deep_analysis.py <clean_folder> <output_folder>
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams["figure.figsize"] = (16, 5)
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False

FOCUS_CATEGORIES = ["Transport", "Food and Non-Alcoholic Beverages"]


def plot_category_vs_overall(long_df, overall, category, out_folder):
    cat_df = long_df[long_df["category"] == category].sort_values("date")
    fig, ax = plt.subplots()
    ax.plot(overall["date"], overall["annual_inflation_pct"], label="Overall",
            color="grey", linewidth=1.5, linestyle="--")
    ax.plot(cat_df["date"], cat_df["yoy_change_pct"], label=category,
            color="#d62728", linewidth=2.5)
    ax.axhline(0, color="grey", linewidth=0.5)
    ax.set_title(f"{category}: Year-on-Year Change vs Overall Inflation")
    ax.set_ylabel("Annual Change (%)")
    ax.legend()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fname = category.split(",")[0].split(" and ")[0].replace(" ", "_").lower()
    path = os.path.join(out_folder, f"{fname}_vs_overall.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def find_extreme_months(long_df, top_n=8):
    """Flag the single most extreme month-over-month category swings -
    these are the specific months worth investigating and explaining."""
    df = long_df.dropna(subset=["mom_change_pct"]).copy()
    df["abs_change"] = df["mom_change_pct"].abs()
    top = df.sort_values("abs_change", ascending=False).head(top_n)
    return top[["date", "category", "mom_change_pct"]]


def main(clean_folder, out_folder):
    os.makedirs(out_folder, exist_ok=True)

    overall = pd.read_csv(os.path.join(clean_folder, "cpi_overall_clean.csv"), parse_dates=["date"])
    long_df = pd.read_csv(os.path.join(clean_folder, "cpi_categories_long.csv"), parse_dates=["date"])

    for cat in FOCUS_CATEGORIES:
        p = plot_category_vs_overall(long_df, overall, cat, out_folder)
        print(f"Saved {p}")

    print("\nMost extreme single-month category swings (investigate these):")
    extremes = find_extreme_months(long_df)
    for _, r in extremes.iterrows():
        direction = "spike" if r["mom_change_pct"] > 0 else "drop"
        print(f"  {r['date'].strftime('%b %Y')}: {r['category']} "
              f"{direction} of {r['mom_change_pct']:+.1f}% (month-over-month)")

    # Transport-specific summary since it's the #1 driver
    transport = long_df[long_df["category"] == "Transport"].sort_values("date")
    print(f"\nTransport year-on-year change range: "
          f"{transport['yoy_change_pct'].min():.1f}% to {transport['yoy_change_pct'].max():.1f}%")
    peak_row = transport.loc[transport["yoy_change_pct"].idxmax()]
    print(f"  Peak Transport inflation: {peak_row['yoy_change_pct']:.1f}% in "
          f"{peak_row['date'].strftime('%B %Y')}")


if __name__ == "__main__":
    clean_folder = sys.argv[1] if len(sys.argv) > 1 else "data/clean"
    out_folder = sys.argv[2] if len(sys.argv) > 2 else "data/analysis"
    main(clean_folder, out_folder)
