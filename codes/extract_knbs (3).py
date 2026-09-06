"""
KNBS CPI Report Extractor
Extracts overall CPI/inflation + 13 COICOP category breakdowns from
KNBS monthly Consumer Price Index PDF releases.

Handles 3 known format variants automatically:
  - Text-based PDFs (2024-2025 era, and 2026 report-style)
  - Scanned/image PDFs (some 2023-era files) -> falls back to OCR
    for the summary figures; table rows are flagged for manual check
    since OCR reliably garbles gridded tables.

Usage:
    python extract_knbs.py <folder_of_pdfs> <output_csv>
"""

import re
import sys
import glob
import os
import csv

import pdfplumber
import pytesseract
from pdf2image import convert_from_path

CATEGORIES = [
    "Food and Non-Alcoholic Beverages",
    "Alcoholic Beverages, Tobacco and Narcotics",
    "Clothing and Footwear",
    "Housing, Water, Electricity, Gas and Other Fuels",
    "Furnishings, Household Equipment and Routine Household Maintenance",
    "Health",
    "Transport",
    "Information and Communication",
    "Recreation, Sport and Culture",
    "Education Services",
    "Restaurants and Accommodation Services",
    "Insurance and Financial Services",
    "Personal Care, Social Protection and Miscellaneous Goods and Services",
]


def get_text_native(pdf_path):
    """Try native text extraction. Returns '' if no text layer exists."""
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text.append(t)
    return "\n".join(full_text)


def get_text_ocr(pdf_path, max_pages=2, poppler_path=None):
    """OCR fallback for scanned PDFs (first N pages only, for speed)."""
    images = convert_from_path(pdf_path, dpi=250, poppler_path=poppler_path)
    full_text = []
    for img in images[:max_pages]:
        full_text.append(pytesseract.image_to_string(img))
    return "\n".join(full_text)


def collapse_whitespace(text):
    return re.sub(r"\s+", " ", text)


def extract_overall(text):
    """Extract annual inflation rate and overall CPI (from->to values)."""
    result = {"annual_inflation_pct": None, "cpi_from": None, "cpi_to": None,
              "monthly_inflation_pct": None}
    text = collapse_whitespace(text)

    m = re.search(
        r"inflation(?:\s+rate)?[^.]*?(?:was|eased to|slowed to|rose to|increased to|declined to|fell to)\s+(\d+\.\d+)\s*per\s*cent",
        text, re.IGNORECASE)
    if m:
        result["annual_inflation_pct"] = float(m.group(1))

    m = re.search(
        r"(?:increased|decreased)\s+from\s+([\d,]+\.\d+)\s+in\b.{0,35}?to\s+([\d,]+\.\d+)",
        text, re.IGNORECASE)
    if m:
        result["cpi_from"] = float(m.group(1).replace(",", ""))
        result["cpi_to"] = float(m.group(2).replace(",", ""))

    m = re.search(
        r"monthly inflation(?:\s+rate)?\s+of\s+(\d+\.\d+)\s*per\s*cent",
        text, re.IGNORECASE)
    if m:
        result["monthly_inflation_pct"] = float(m.group(1))

    return result


def extract_categories(text):
    """Extract per-category weight%, monthly change%, yearly change% via
    fixed-name anchoring (robust across table-numbering/layout changes)."""
    flat = collapse_whitespace(text)
    rows = {}
    for cat in CATEGORIES:
        # category name, then weight (4 decimals typical), then two signed % changes
        pattern = re.escape(cat) + r"\s+([\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)"
        m = re.search(pattern, flat)
        if m:
            rows[cat] = {
                "weight_pct": float(m.group(1)),
                "change_month_pct": float(m.group(2)),
                "change_year_pct": float(m.group(3)),
            }
        else:
            rows[cat] = None
    return rows


def extract_month_year_from_filename(path):
    fname = os.path.basename(path)
    m = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)[-\s]?(\d{4})",
        fname, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    return None, None


def process_pdf(path, poppler_path=None):
    text = get_text_native(path)
    used_ocr = False
    if len(text.strip()) < 200:  # effectively no text layer -> scanned PDF
        text = get_text_ocr(path, poppler_path=poppler_path)
        used_ocr = True

    month, year = extract_month_year_from_filename(path)
    overall = extract_overall(text)
    categories = extract_categories(text)

    n_missing = sum(1 for v in categories.values() if v is None)
    low_confidence = used_ocr or n_missing > 0

    row = {
        "file": os.path.basename(path),
        "month": month,
        "year": year,
        "used_ocr": used_ocr,
        "low_confidence_flag": low_confidence,
        "categories_found": 13 - n_missing,
        **{f"annual_inflation_pct": overall["annual_inflation_pct"]},
        **{f"monthly_inflation_pct": overall["monthly_inflation_pct"]},
        **{f"cpi_from": overall["cpi_from"]},
        **{f"cpi_to": overall["cpi_to"]},
    }
    for cat, vals in categories.items():
        short = cat.split(",")[0].split(" and ")[0].strip().replace(" ", "_")[:20]
        if vals:
            row[f"{short}_weight"] = vals["weight_pct"]
            row[f"{short}_mom_pct"] = vals["change_month_pct"]
            row[f"{short}_yoy_pct"] = vals["change_year_pct"]
        else:
            row[f"{short}_weight"] = None
            row[f"{short}_mom_pct"] = None
            row[f"{short}_yoy_pct"] = None
    return row


def load_existing(out_csv):
    """Load already-processed rows so we don't reprocess or overwrite them.
    Returns (list_of_row_dicts, set_of_already_processed_filenames)."""
    if not os.path.exists(out_csv):
        return [], set()
    with open(out_csv, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    processed_files = {r["file"] for r in rows}
    return rows, processed_files


def main(folder, out_csv, poppler_path=None):
    pdfs = sorted(glob.glob(os.path.join(folder, "*.pdf")))
    if not pdfs:
        print(f"No PDFs found in {folder}")
        return

    existing_rows, already_processed = load_existing(out_csv)
    if already_processed:
        print(f"Found existing {out_csv} with {len(existing_rows)} row(s) already processed "
              f"(these will be kept as-is, including any manual edits you made).\n")

    new_pdfs = [p for p in pdfs if os.path.basename(p) not in already_processed]
    skipped = len(pdfs) - len(new_pdfs)
    if skipped:
        print(f"Skipping {skipped} PDF(s) already in {out_csv}.")
    if not new_pdfs:
        print("Nothing new to process - every PDF in the folder is already in the CSV.")
        return

    print(f"Processing {len(new_pdfs)} new PDF(s)...\n")
    new_rows = []
    for p in new_pdfs:
        print(f"Processing {os.path.basename(p)}...")
        try:
            row = process_pdf(p, poppler_path=poppler_path)
            new_rows.append(row)
            flag = " [LOW CONFIDENCE - check manually]" if row["low_confidence_flag"] else ""
            print(f"  -> {row['month']} {row['year']}: "
                  f"annual inflation {row['annual_inflation_pct']}%, "
                  f"{row['categories_found']}/13 categories found{flag}")
        except Exception as e:
            print(f"  -> FAILED: {e}")

    if new_rows:
        # Convert new_rows (dicts with float/bool values) to strings matching
        # existing_rows format (all strings, since csv.DictReader reads everything as text)
        all_rows = existing_rows + [{k: str(v) for k, v in r.items()} for r in new_rows]
        keys = list(new_rows[0].keys())
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\nAdded {len(new_rows)} new row(s). {out_csv} now has {len(all_rows)} total rows.")
        n_flagged = sum(1 for r in new_rows if r["low_confidence_flag"])
        if n_flagged:
            print(f"{n_flagged} new file(s) flagged for manual review (scanned or incomplete extraction).")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "data/clean/cpi_extracted.csv"
    poppler_path = sys.argv[3] if len(sys.argv) > 3 else None
    out_dir = os.path.dirname(out_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    main(folder, out_csv, poppler_path=poppler_path)
