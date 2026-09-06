# Kenya Cost of Living Analysis: CPI Trends, July 2023 - July 2026

A data pipeline and analysis of Kenya's Consumer Price Index (CPI) and inflation,
built from 37 monthly reports published by the Kenya National Bureau of Statistics
(KNBS). The project traces how the cost of living moved over three years, identifies
which spending categories drove it, and investigates the real-world events behind
the largest anomalies.

## The question

How has Kenya's cost of living changed between July 2023 and July 2026, and what
drove the biggest shifts?

## Data source

37 monthly "Consumer Price Indices and Inflation Rates" PDF reports, downloaded
directly from [knbs.or.ke](https://www.knbs.or.ke). Each report publishes the
overall CPI, the year-on-year inflation rate, and a breakdown across 13 standardized
expenditure categories (COICOP divisions) covering everything from food to
insurance.

## Pipeline

Four scripts, run in order, each producing the input for the next:

| Script | What it does | Output |
|---|---|---|
| `extract_knbs.py` | Pulls structured data out of each PDF - handles three different report layouts KNBS used across the period, plus a fallback OCR path for scanned/image-based reports | `cpi_extracted.csv` |
| `clean_cpi.py` | Parses dates, removes duplicates, flags missing months, and recovers missing CPI values by chaining consecutive months' stated start/end points | `cpi_overall_clean.csv`, `cpi_categories_long.csv`, `cpi_full_wide.csv` |
| `eda_cpi.py` | First-look exploratory charts: overall CPI trend, inflation rate trend, category ranking by cumulative change | PNG charts |
| `deep_analysis.py` | Zooms into the top categories (Transport, Food) against the overall trend; flags the single biggest month-over-month swings | PNG charts, console report |
| `anomaly_detector.py` | Statistical anomaly detection - flags any category's month where it moved unusually far from *its own* historical average (z-score method, not a fixed global threshold) | `anomalies_report.csv`, PNG charts |

**A note on data quality:** roughly 5 of the 37 source PDFs were scanned images
rather than digital text, meaning their category tables couldn't be reliably
OCR'd. Those specific months' category-level figures were manually verified
against the original PDF tables rather than guessed at. This is documented
rather than hidden, since knowing the limits of your own pipeline is part of
doing the analysis honestly.

## Key findings

**Overall:** CPI rose from 134.15 to 155.20 over the three years - a 15.7% total
increase. Annual inflation started at 7.3% (July 2023), cooled to a low of 2.7%
(October 2024), then climbed back to 6.5% by July 2026.

**Transport was the most volatile category**, and its swings map directly onto
three distinct, verifiable real-world events:
- **July-September 2023:** VAT on fuel doubled from 8% to 16% under the Finance
  Act 2023, pushing pump prices past KSh 200/litre for the first time in Kenyan
  history.
- **December 2024:** a holiday-season matatu fare surge (up to 50% on some
  routes) drove Transport costs up even as fuel prices *fell* that month -
  showing Transport inflation isn't only about fuel.
- **April-May 2026:** a Middle East conflict disrupted global oil supply,
  pushing Kenyan diesel to an all-time historic high despite a temporary
  government VAT cut intended to cushion the impact.

**Food and Non-Alcoholic Beverages was the steadier driver** - consistently
above the overall inflation line for nearly the entire period, reflecting
sustained pressure on everyday grocery costs rather than one-off shocks.

**The largest single statistical anomaly in the whole dataset** was actually
Clothing and Footwear in December 2024 (+2.0% in one month, a 5-standard-deviation
outlier for that usually-stable category) - and notably, KNBS's own report
commentary didn't mention it at all, suggesting it went unremarked even by the
people who published the data.

## Tools

Python (pandas, matplotlib, pdfplumber, pytesseract for OCR fallback), with
final visualization in [Power BI / Tableau - fill in whichever you use].

## Limitations

- December 2023's category-level breakdown is incomplete (recovered from a
  later report's historical summary table rather than its own dedicated release)
- A handful of months relied on manual verification against scanned PDFs rather
  than fully automated extraction
- Anomaly detection is based on only 37 months of history per category, so
  z-scores are a useful signal for investigation, not a statistically airtight
  threshold

## Repository structure

```
codes/              extraction, cleaning, and analysis scripts
data/raw/            original downloaded PDFs
data/extracted/      raw extraction output (cpi_extracted.csv)
data/clean/          cleaned, analysis-ready datasets
data/eda/            exploratory charts
data/analysis/       deep-dive and anomaly detection charts
```
