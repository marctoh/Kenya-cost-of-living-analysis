"""
Day 2: Clean and merge the 36 extracted KNBS CPI rows into a tidy,
analysis-ready time series.

What this does:
  1. Parses month/year into a real date, sorts chronologically
  2. Checks for duplicate or missing months
  3. Reconstructs missing overall CPI index values by chaining
     (each month's cpi_to should equal the next month's cpi_from —
     so a gap in one can often be filled from its neighbor)
  4. Outputs three clean files:
       - cpi_overall_clean.csv   (one row per month: date, CPI, inflation)
       - cpi_categories_long.csv (tidy long format: date, category, weight,
                                   mom%, yoy% — ideal for Power BI/Tableau)
       - cpi_full_wide.csv       (everything in one wide table, for reference)

Usage:
    python clean_cpi.py <input_csv> <output_folder>
"""

import sys
import os
import pandas as pd

MONTH_NUM = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}

CATEGORY_SHORT_NAMES = [
    "Food", "Alcoholic_Beverages", "Clothing", "Housing", "Furnishings",
    "Health", "Transport", "Information", "Recreation", "Education_Services",
    "Restaurants", "Insurance", "Personal_Care",
]

CATEGORY_FULL_NAMES = {
    "Food": "Food and Non-Alcoholic Beverages",
    "Alcoholic_Beverages": "Alcoholic Beverages, Tobacco and Narcotics",
    "Clothing": "Clothing and Footwear",
    "Housing": "Housing, Water, Electricity, Gas and Other Fuels",
    "Furnishings": "Furnishings, Household Equipment and Routine Household Maintenance",
    "Health": "Health",
    "Transport": "Transport",
    "Information": "Information and Communication",
    "Recreation": "Recreation, Sport and Culture",
    "Education_Services": "Education Services",
    "Restaurants": "Restaurants and Accommodation Services",
    "Insurance": "Insurance and Financial Services",
    "Personal_Care": "Personal Care, Social Protection and Miscellaneous Goods and Services",
}


def load_and_dedupe(path):
    df = pd.read_csv(path)
    df["month_num"] = df["month"].map(MONTH_NUM)
    df["date"] = pd.to_datetime(dict(year=df["year"], month=df["month_num"], day=1))

    n_before = len(df)
    dupes = df[df.duplicated(subset="date", keep=False)]
    if len(dupes) > 0:
        print(f"WARNING: {len(dupes)} duplicate month(s) found:")
        print(dupes[["file", "date"]].to_string(index=False))
        df = df.drop_duplicates(subset="date", keep="first")
        print(f"  -> kept first occurrence, dropped {n_before - len(df)} duplicate row(s)")

    df = df.sort_values("date").reset_index(drop=True)
    return df


def check_gaps(df):
    full_range = pd.date_range(df["date"].min(), df["date"].max(), freq="MS")
    missing = sorted(set(full_range) - set(df["date"]))
    if missing:
        print(f"\nNOTE: {len(missing)} month(s) missing from your file set entirely "
              f"(no PDF downloaded for these):")
        for m in missing:
            print(f"  - {m.strftime('%B %Y')}")
    return missing


def reconstruct_cpi_levels(df):
    """Chain-fill missing cpi_from/cpi_to: month[i].cpi_to should equal
    month[i+1].cpi_from, so a gap in one can be filled from the other."""
    df = df.copy()
    n_filled = 0
    # forward pass: fill cpi_from[i] using cpi_to[i-1]
    for i in range(1, len(df)):
        if pd.isna(df.loc[i, "cpi_from"]) and not pd.isna(df.loc[i - 1, "cpi_to"]):
            df.loc[i, "cpi_from"] = df.loc[i - 1, "cpi_to"]
            n_filled += 1
    # backward pass: fill cpi_to[i] using cpi_from[i+1]
    for i in range(len(df) - 2, -1, -1):
        if pd.isna(df.loc[i, "cpi_to"]) and not pd.isna(df.loc[i + 1, "cpi_from"]):
            df.loc[i, "cpi_to"] = df.loc[i + 1, "cpi_from"]
            n_filled += 1
    # one more forward pass in case backward pass unlocked new forward fills
    for i in range(1, len(df)):
        if pd.isna(df.loc[i, "cpi_from"]) and not pd.isna(df.loc[i - 1, "cpi_to"]):
            df.loc[i, "cpi_from"] = df.loc[i - 1, "cpi_to"]
            n_filled += 1

    still_missing = df[df["cpi_from"].isna() | df["cpi_to"].isna()]
    print(f"\nReconstructed {n_filled} missing CPI value(s) via chaining.")
    if len(still_missing) > 0:
        print(f"{len(still_missing)} month(s) still have gaps (no chain neighbor available):")
        print(still_missing[["file", "date"]].to_string(index=False))

    # recompute monthly inflation % anywhere it's missing but we now have both ends
    mask = df["monthly_inflation_pct"].isna() & df["cpi_from"].notna() & df["cpi_to"].notna()
    df.loc[mask, "monthly_inflation_pct"] = (
        (df.loc[mask, "cpi_to"] / df.loc[mask, "cpi_from"] - 1) * 100
    ).round(2)

    return df


def build_overall(df):
    return df[["date", "cpi_from", "cpi_to", "monthly_inflation_pct", "annual_inflation_pct"]].rename(
        columns={"cpi_to": "overall_cpi", "cpi_from": "prev_month_cpi"}
    )


def build_long(df):
    rows = []
    for _, r in df.iterrows():
        for short in CATEGORY_SHORT_NAMES:
            rows.append({
                "date": r["date"],
                "category": CATEGORY_FULL_NAMES[short],
                "weight_pct": r.get(f"{short}_weight"),
                "mom_change_pct": r.get(f"{short}_mom_pct"),
                "yoy_change_pct": r.get(f"{short}_yoy_pct"),
            })
    return pd.DataFrame(rows)


def main(in_csv, out_folder):
    os.makedirs(out_folder, exist_ok=True)
    df = load_and_dedupe(in_csv)
    print(f"Loaded {len(df)} unique months, {df['date'].min().strftime('%b %Y')} "
          f"to {df['date'].max().strftime('%b %Y')}")

    check_gaps(df)
    df = reconstruct_cpi_levels(df)

    overall = build_overall(df)
    long_df = build_long(df)

    overall_path = os.path.join(out_folder, "cpi_overall_clean.csv")
    long_path = os.path.join(out_folder, "cpi_categories_long.csv")
    wide_path = os.path.join(out_folder, "cpi_full_wide.csv")

    overall.to_csv(overall_path, index=False)
    long_df.to_csv(long_path, index=False)
    df.to_csv(wide_path, index=False)

    print(f"\nSaved:")
    print(f"  {overall_path}  ({len(overall)} rows) — main trend line")
    print(f"  {long_path}  ({len(long_df)} rows) — tidy, for dashboard/category charts")
    print(f"  {wide_path}  ({len(df)} rows) — full reference table")


if __name__ == "__main__":
    in_csv = sys.argv[1] if len(sys.argv) > 1 else "cpi_extracted.csv"
    out_folder = sys.argv[2] if len(sys.argv) > 2 else "data/clean"
    main(in_csv, out_folder)
