import argparse
import math
import re
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "calendars"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "calendars"
RESULTS_DIR = PROJECT_ROOT / "results" / "calendars"

EXPECTED_COLUMNS = [
    "listing_id",
    "date",
    "available",
    "price",
    "adjusted_price",
    "minimum_nights",
    "maximum_nights",
]
CHUNK_SIZE = 200_000
PRICE_CLEAN_PATTERN = re.compile(r"[^0-9.\-]")


def render_progress(prefix: str, current: int, total: int) -> None:
    if total <= 0:
        return
    width = 28
    ratio = min(max(current / total, 0), 1)
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    percent = ratio * 100
    sys.stdout.write(f"\r{prefix} [{bar}] {percent:6.2f}%")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


def normalize_price(series: pd.Series) -> pd.Series:
    cleaned = (
        series.fillna("")
        .astype(str)
        .str.replace(PRICE_CLEAN_PATTERN, "", regex=True)
        .replace("", pd.NA)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_available(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip().str.lower()
    mapped = normalized.map(
        {
            "t": True,
            "true": True,
            "1": True,
            "f": False,
            "false": False,
            "0": False,
        }
    )
    return mapped.astype("boolean")


def city_name_from_file(path: Path) -> str:
    city = path.stem.replace("calendar_", "")
    return city.replace("_", "")


def process_city(csv_file: Path) -> dict:
    city = city_name_from_file(csv_file)
    output_file = PROCESSED_DIR / f"{city}_calendar_cleaned.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists():
        output_file.unlink()

    total_size = csv_file.stat().st_size
    rows_in = 0
    rows_out = 0
    duplicate_rows_removed = 0
    missing_required_rows_removed = 0
    invalid_date_rows_removed = 0
    invalid_available_rows_removed = 0
    price_missing_before = 0
    adjusted_price_missing_before = 0
    price_non_null_after = 0
    adjusted_price_non_null_after = 0
    available_true_rows = 0
    available_false_rows = 0
    min_nights_missing_after = 0
    max_nights_missing_after = 0
    seen_hashes = set()

    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        for chunk_index, chunk in enumerate(pd.read_csv(handle, usecols=EXPECTED_COLUMNS, chunksize=CHUNK_SIZE)):
            rows_in += len(chunk)

            row_hashes = pd.util.hash_pandas_object(chunk[EXPECTED_COLUMNS], index=False)
            duplicate_mask = row_hashes.isin(seen_hashes)
            duplicate_rows_removed += int(duplicate_mask.sum())
            seen_hashes.update(row_hashes[~duplicate_mask].tolist())

            filtered = chunk.loc[~duplicate_mask].copy()

            required_non_missing = filtered[["listing_id", "date", "available"]].notna().all(axis=1)
            missing_required_rows_removed += int((~required_non_missing).sum())
            filtered = filtered.loc[required_non_missing].copy()

            filtered["date"] = pd.to_datetime(filtered["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            invalid_date_mask = filtered["date"].isna()
            invalid_date_rows_removed += int(invalid_date_mask.sum())
            filtered = filtered.loc[~invalid_date_mask].copy()

            filtered["available"] = normalize_available(filtered["available"])
            invalid_available_mask = filtered["available"].isna()
            invalid_available_rows_removed += int(invalid_available_mask.sum())
            filtered = filtered.loc[~invalid_available_mask].copy()

            price_missing_before += int(filtered["price"].isna().sum()) + int(
                filtered["price"].fillna("").astype(str).str.strip().eq("").sum()
            )
            adjusted_price_missing_before += int(filtered["adjusted_price"].isna().sum()) + int(
                filtered["adjusted_price"].fillna("").astype(str).str.strip().eq("").sum()
            )

            filtered["price"] = normalize_price(filtered["price"])
            filtered["adjusted_price"] = normalize_price(filtered["adjusted_price"])
            filtered["minimum_nights"] = pd.to_numeric(filtered["minimum_nights"], errors="coerce").astype("Int64")
            filtered["maximum_nights"] = pd.to_numeric(filtered["maximum_nights"], errors="coerce").astype("Int64")
            filtered["available"] = filtered["available"].astype(bool)

            price_non_null_after += int(filtered["price"].notna().sum())
            adjusted_price_non_null_after += int(filtered["adjusted_price"].notna().sum())
            available_true_rows += int(filtered["available"].sum())
            available_false_rows += int((~filtered["available"]).sum())
            min_nights_missing_after += int(filtered["minimum_nights"].isna().sum())
            max_nights_missing_after += int(filtered["maximum_nights"].isna().sum())

            rows_out += len(filtered)
            filtered.to_csv(
                output_file,
                mode="w" if chunk_index == 0 else "a",
                index=False,
                header=chunk_index == 0,
            )

            try:
                render_progress(f"{city:14}", handle.tell(), total_size)
            except OSError:
                pass

    percent_removed = 0 if rows_in == 0 else round(((rows_in - rows_out) / rows_in) * 100, 2)

    return {
        "city": city,
        "source_file": str(csv_file.relative_to(PROJECT_ROOT)),
        "output_file": str(output_file.relative_to(PROJECT_ROOT)),
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_removed_total": rows_in - rows_out,
        "percent_removed": percent_removed,
        "duplicate_rows_removed": duplicate_rows_removed,
        "missing_required_rows_removed": missing_required_rows_removed,
        "invalid_date_rows_removed": invalid_date_rows_removed,
        "invalid_available_rows_removed": invalid_available_rows_removed,
        "price_missing_before": price_missing_before,
        "adjusted_price_missing_before": adjusted_price_missing_before,
        "price_non_null_after": price_non_null_after,
        "adjusted_price_non_null_after": adjusted_price_non_null_after,
        "available_true_rows": available_true_rows,
        "available_false_rows": available_false_rows,
        "minimum_nights_missing_after": min_nights_missing_after,
        "maximum_nights_missing_after": max_nights_missing_after,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean Airbnb calendar files and create one cleaned CSV per city plus an audit CSV."
    )
    parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    input_files = sorted(RAW_DIR.glob("calendar_*.csv"))
    if not input_files:
        raise FileNotFoundError(f"No calendar CSV files found in {RAW_DIR}")

    audit_rows = []
    print(f"Cleaning {len(input_files)} calendar files")
    for csv_file in input_files:
        print(f"Starting {csv_file.name}")
        result = process_city(csv_file)
        audit_rows.append(result)
        print(
            f"Finished {result['city']}: rows_in={result['rows_in']}, "
            f"rows_out={result['rows_out']}, removed={result['rows_removed_total']}"
        )

    audit_df = pd.DataFrame(audit_rows)
    audit_path = RESULTS_DIR / "calendars_cleaning_audit.csv"
    audit_df.to_csv(audit_path, index=False)
    print(f"Saved audit summary to {audit_path}")


if __name__ == "__main__":
    main()
