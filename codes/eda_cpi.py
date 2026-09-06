"""
Day 3: Exploratory Data Analysis on the cleaned KNBS CPI data.

Produces:
  1. overall_cpi_trend.png    - the headline CPI index over time
  2. annual_inflation_trend.png - the year-on-year inflation rate over time
  3. category_total_change.png  - which of the 13 categories rose the most
                                   over the full period (weight-independent,
                                   pure cumulative % change), ranked

Usage:
    python eda_cpi.py <clean_folder> <output_folder>
    (expects cpi_overall_clean.csv and cpi_categories_long.csv in clean_folder)
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams["figure.figsize"] = (16, 5)
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False


def plot_overall_cpi(overall, out_folder):
    fig, ax = plt.subplots()
    ax.plot(overall["date"], overall["overall_cpi"], color="#1f77b4", linewidth=2)
    ax.set_title("Kenya Overall CPI, July 2023 - July 2026 (Base Feb 2019 = 100)")
    ax.set_ylabel("CPI Index")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    path = os.path.join(out_folder, "overall_cpi_trend.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def plot_annual_inflation(overall, out_folder):
    fig, ax = plt.subplots()
    ax.plot(overall["date"], overall["annual_inflation_pct"], color="#d62728", linewidth=2)
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_title("Kenya Year-on-Year Inflation Rate, July 2023 - July 2026")
    ax.set_ylabel("Annual Inflation (%)")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    path = os.path.join(out_folder, "annual_inflation_trend.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def compute_cumulative_change(long_df):
    """For each category, compound its month-over-month % changes into a
    synthetic index starting at 100, then report total % change over the
    full period. This ranks categories independent of their weight."""
    results = []
    for cat, g in long_df.groupby("category"):
        g = g.sort_values("date")
        index = 100.0
        for mom in g["mom_change_pct"]:
            if pd.notna(mom):
                index *= (1 + mom / 100)
        total_change = index - 100.0
        results.append({"category": cat, "total_change_pct": total_change})
    return pd.DataFrame(results).sort_values("total_change_pct", ascending=True)


def plot_category_ranking(long_df, out_folder):
    ranked = compute_cumulative_change(long_df)
    fig, ax = plt.subplots(figsize=(10, 7))
    colors = ["#d62728" if v > ranked["total_change_pct"].median() else "#1f77b4"
              for v in ranked["total_change_pct"]]
    ax.barh(ranked["category"], ranked["total_change_pct"], color=colors)
    ax.set_title("Total Price Change by Category, July 2023 - July 2026")
    ax.set_xlabel("Cumulative Change (%)")
    plt.tight_layout()
    path = os.path.join(out_folder, "category_total_change.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path, ranked


def main(clean_folder, out_folder):
    os.makedirs(out_folder, exist_ok=True)

    overall = pd.read_csv(os.path.join(clean_folder, "cpi_overall_clean.csv"), parse_dates=["date"])
    long_df = pd.read_csv(os.path.join(clean_folder, "cpi_categories_long.csv"), parse_dates=["date"])

    p1 = plot_overall_cpi(overall, out_folder)
    print(f"Saved {p1}")

    p2 = plot_annual_inflation(overall, out_folder)
    print(f"Saved {p2}")

    p3, ranked = plot_category_ranking(long_df, out_folder)
    print(f"Saved {p3}")

    print("\nCategory ranking (total cumulative change over the period):")
    print(ranked.sort_values("total_change_pct", ascending=False).to_string(index=False))

    print("\nQuick headline stats:")
    print(f"  Overall CPI: {overall['overall_cpi'].iloc[0]:.2f} -> {overall['overall_cpi'].iloc[-1]:.2f}")
    total_pct = (overall['overall_cpi'].iloc[-1] / overall['overall_cpi'].iloc[0] - 1) * 100
    print(f"  Total change over period: {total_pct:.1f}%")
    print(f"  Highest annual inflation reading: {overall['annual_inflation_pct'].max():.1f}% "
          f"({overall.loc[overall['annual_inflation_pct'].idxmax(), 'date'].strftime('%B %Y')})")
    print(f"  Lowest annual inflation reading: {overall['annual_inflation_pct'].min():.1f}% "
          f"({overall.loc[overall['annual_inflation_pct'].idxmin(), 'date'].strftime('%B %Y')})")


if __name__ == "__main__":
    clean_folder = sys.argv[1] if len(sys.argv) > 1 else "data/clean"
    out_folder = sys.argv[2] if len(sys.argv) > 2 else "data/eda"
    main(clean_folder, out_folder)
