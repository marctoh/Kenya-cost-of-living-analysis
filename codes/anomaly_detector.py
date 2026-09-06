"""
Automated Anomaly Detection for KNBS CPI data.

Instead of manually eyeballing "biggest swings" (like deep_analysis.py does),
this uses a statistical method: for each category, it calculates that
category's own normal month-to-month volatility, then flags any month
that's unusually extreme FOR THAT CATEGORY specifically.

Why per-category thresholds matter: Transport naturally swings a lot
(fuel prices), so a 3% Transport move might be normal. Insurance barely
moves at all, so even a 1% Insurance swing could be a genuine anomaly.
A single global threshold would miss this - flag too much in volatile
categories, too little in stable ones.

Method: z-score. For each category, compute mean and standard deviation
of its month-over-month % changes across the whole dataset. Flag any
month where that category's change is more than N standard deviations
from ITS OWN average (default N=2, which flags roughly the most unusual
5% of readings).

Usage:
    python anomaly_detector.py <clean_folder> <output_folder> [threshold]
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams["figure.figsize"] = (16, 6)
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False

DEFAULT_THRESHOLD = 2.0  # standard deviations


def detect_anomalies(long_df, threshold):
    results = []
    for cat, g in long_df.groupby("category"):
        g = g.dropna(subset=["mom_change_pct"]).sort_values("date")
        mean = g["mom_change_pct"].mean()
        std = g["mom_change_pct"].std()
        if std == 0 or pd.isna(std):
            continue
        g = g.copy()
        g["z_score"] = (g["mom_change_pct"] - mean) / std
        flagged = g[g["z_score"].abs() >= threshold]
        for _, r in flagged.iterrows():
            results.append({
                "date": r["date"],
                "category": cat,
                "mom_change_pct": r["mom_change_pct"],
                "category_avg_change": round(mean, 2),
                "category_typical_swing": round(std, 2),
                "z_score": round(r["z_score"], 2),
                "direction": "SPIKE" if r["z_score"] > 0 else "DROP",
            })
    return pd.DataFrame(results).sort_values("z_score", key=abs, ascending=False)


def check_overall_anomalies(overall, threshold):
    """Same idea but for the headline monthly inflation figure."""
    df = overall.dropna(subset=["monthly_inflation_pct"]).copy()
    mean = df["monthly_inflation_pct"].mean()
    std = df["monthly_inflation_pct"].std()
    df["z_score"] = (df["monthly_inflation_pct"] - mean) / std
    return df[df["z_score"].abs() >= threshold][["date", "monthly_inflation_pct", "z_score"]]


def plot_anomaly_scatter(cat_anomalies, out_folder):
    """Every flagged anomaly plotted over time, colored by severity."""
    if len(cat_anomalies) == 0:
        return None
    fig, ax = plt.subplots()
    colors = ["#d62728" if d == "SPIKE" else "#1f77b4" for d in cat_anomalies["direction"]]
    sizes = (cat_anomalies["z_score"].abs() * 40).clip(lower=40)
    ax.scatter(cat_anomalies["date"], cat_anomalies["z_score"], c=colors, s=sizes,
               alpha=0.75, edgecolors="black", linewidths=0.5)
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_title("Flagged Anomalies Over Time (bubble size = severity)")
    ax.set_ylabel("Z-score (how unusual, for that category)")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45, ha="right")
    # label only the most extreme points to avoid clutter
    top_labels = cat_anomalies.reindex(cat_anomalies["z_score"].abs().sort_values(ascending=False).index).head(6)
    for _, r in top_labels.iterrows():
        short_cat = r["category"].split(",")[0].split(" and ")[0]
        ax.annotate(short_cat, (r["date"], r["z_score"]), fontsize=8,
                    xytext=(5, 5), textcoords="offset points")
    plt.tight_layout()
    path = os.path.join(out_folder, "anomaly_scatter.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def plot_overall_with_anomalies(overall, overall_anomalies, out_folder):
    fig, ax = plt.subplots()
    ax.plot(overall["date"], overall["monthly_inflation_pct"], color="grey",
            linewidth=1.5, label="Monthly inflation")
    if len(overall_anomalies) > 0:
        ax.scatter(overall_anomalies["date"], overall_anomalies["monthly_inflation_pct"],
                   color="#d62728", s=100, zorder=5, label="Anomalous month", edgecolors="black")
    ax.axhline(0, color="grey", linewidth=0.5)
    ax.set_title("Monthly Inflation with Anomalous Months Highlighted")
    ax.set_ylabel("Monthly Inflation (%)")
    ax.legend()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    path = os.path.join(out_folder, "overall_anomalies_highlighted.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def main(clean_folder, out_folder, threshold=DEFAULT_THRESHOLD):
    os.makedirs(out_folder, exist_ok=True)

    overall = pd.read_csv(os.path.join(clean_folder, "cpi_overall_clean.csv"), parse_dates=["date"])
    long_df = pd.read_csv(os.path.join(clean_folder, "cpi_categories_long.csv"), parse_dates=["date"])

    print(f"Detecting anomalies using a {threshold}-standard-deviation threshold "
          f"(per category, based on that category's own historical volatility)...\n")

    cat_anomalies = detect_anomalies(long_df, threshold)
    overall_anomalies = check_overall_anomalies(overall, threshold)

    if len(cat_anomalies) == 0:
        print("No category-level anomalies found at this threshold.")
    else:
        print(f"Found {len(cat_anomalies)} category-level anomaly month(s):\n")
        for _, r in cat_anomalies.iterrows():
            print(f"  [{r['direction']}] {r['date'].strftime('%b %Y')} - {r['category']}: "
                  f"{r['mom_change_pct']:+.1f}% (this category normally moves "
                  f"{r['category_avg_change']:+.1f}% +/- {r['category_typical_swing']:.1f}%, "
                  f"z-score={r['z_score']})")

    if len(overall_anomalies) > 0:
        print(f"\nOverall inflation anomaly month(s):")
        for _, r in overall_anomalies.iterrows():
            print(f"  {r['date'].strftime('%b %Y')}: monthly inflation {r['monthly_inflation_pct']:+.1f}% "
                  f"(z-score={r['z_score']:.2f})")

    out_path = os.path.join(out_folder, "anomalies_report.csv")
    cat_anomalies.to_csv(out_path, index=False)
    print(f"\nSaved full report to {out_path}")

    p1 = plot_anomaly_scatter(cat_anomalies, out_folder)
    if p1:
        print(f"Saved {p1}")
    p2 = plot_overall_with_anomalies(overall, overall_anomalies, out_folder)
    print(f"Saved {p2}")

    print(f"\nTip: lower the threshold (e.g. 1.5) to flag more months, "
          f"raise it (e.g. 2.5) to flag only the most extreme ones.")


if __name__ == "__main__":
    clean_folder = sys.argv[1] if len(sys.argv) > 1 else "data/clean"
    out_folder = sys.argv[2] if len(sys.argv) > 2 else "data/analysis"
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_THRESHOLD
    main(clean_folder, out_folder, threshold)
