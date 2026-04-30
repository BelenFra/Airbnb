"""Calendar cleaning pipeline for the MBA706 Term Project.

Reads raw Inside Airbnb calendar files from
    data/raw/calendars/calendar_<snake_city>.csv
and produces, in a single streaming pass per city:

* data/processed/calendar/<city>/calendar_<city>_cleaned.csv   (per-city, row-level, optional)
* data/processed/calendar/<city>/occupation_<city>_cleaned.csv (per-city, listing-level)
* data/processed/calendar_all_cleaned.csv                      (merged row-level, optional)
* data/processed/occupation_all_cleaned.csv                    (merged listing-level)
* results/01_market_analysis/calendars/calendars_cleaning_audit.csv             (per-city audit)

Cleaning rules and occupancy definition are documented in
    scripts/cleaning/calendars/calendar_cleaning_decisions.md

Listing prices for revenue estimation come from the cleaned listings master:
    data/processed/listing_all_cleaned.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("MPLCONFIGDIR", ".cache/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", ".cache")
os.environ.setdefault("MPLBACKEND", "Agg")

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

RAW_ROOT = PROJECT_ROOT / "data" / "raw"
RAW_CALENDARS_DIR = RAW_ROOT / "calendars"
PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"
STANDARD_CALENDAR_DIR = PROJECT_ROOT / "data" / "processed" / "calendar"
RESULTS_DIR = PROJECT_ROOT / "results" / "01_market_analysis" / "calendars"

CITY_LABEL_BY_SNAKE = {
    "hawaii": "Hawaii",
    "los_angeles": "Los Angeles",
    "nashville": "Nashville",
    "new_york": "New York",
    "san_francisco": "San Francisco",
}

# Inverse direction (label -> snake). Restored on purpose: we need this every
# time we read another layer that still carries the human-readable city label
# (e.g. the listings master uses `City = "Los Angeles"` today). Keep the two
# dicts in sync; do not duplicate values manually.
CITY_NAME_MAP = {label: snake for snake, label in CITY_LABEL_BY_SNAKE.items()}

EXPECTED_COLUMNS = [
    "listing_id",
    "date",
    "available",
    "price",
    "adjusted_price",
    "minimum_nights",
    "maximum_nights",
]

OUTPUT_ROW_COLUMNS = [
    "listing_id",
    "city",
    "date",
    "available",
    "price",
    "adjusted_price",
    "minimum_nights",
    "maximum_nights",
]

CHUNK_SIZE = 200_000
PRICE_CLEAN_PATTERN = re.compile(r"[^0-9.\-]")
# Outlier hard caps (restored from PR #1 / commit 9de6204 by Yu Wang).
# Documented in scripts/cleaning/calendars/calendar_cleaning_decisions.md §3.8.
# These are *platform-level* sanity caps (not statistical clipping). Per-city
# quantile-based clipping for modeling stays out of the cleaner on purpose.
PRICE_HARD_CAP = 10_000.0
NIGHTS_HARD_CAP = 1125
ALL_CITIES_ROW_FILE = PROCESSED_ROOT / "calendar_all_cleaned.csv"
ALL_CITIES_LISTING_FILE = PROJECT_ROOT / "data" / "processed" / "occupation_all_cleaned.csv"
AUDIT_FILE = RESULTS_DIR / "calendars_cleaning_audit.csv"
CLEANED_LISTINGS_FILE = PROJECT_ROOT / "data" / "processed" / "listing_all_cleaned.csv"
MISSING_TEXT_VALUES = {"": pd.NA, "nan": pd.NA, "None": pd.NA}
RANDOM_STATE = 42


def load_listing_prices(city_label: str) -> pd.DataFrame:
    """Read cleaned listings and return [listing_id, listing_price] for one city.

    Calendar price columns are empty in the raw data, so revenue estimation uses
    the final cleaned listings file instead of reparsing raw city listings here.
    """
    if not CLEANED_LISTINGS_FILE.exists():
        raise FileNotFoundError(
            f"Missing cleaned listing file: {CLEANED_LISTINGS_FILE}. "
            "Run scripts/cleaning/listing/run_full_listing_cleaning.py first."
        )

    df = pd.read_csv(
        CLEANED_LISTINGS_FILE,
        usecols=["id", "price", "City"],
        encoding="utf-8-sig",
        low_memory=False,
    )
    df = df.loc[df["City"].eq(city_label), ["id", "price"]].copy()
    df = df.rename(columns={"id": "listing_id", "price": "listing_price"})
    df["listing_id"] = normalize_listing_id(df["listing_id"])
    df["listing_price"] = pd.to_numeric(df["listing_price"], errors="coerce")
    df.loc[df["listing_price"] > PRICE_HARD_CAP, "listing_price"] = pd.NA
    df = df.dropna(subset=["listing_id"])
    return df[["listing_id", "listing_price"]].drop_duplicates("listing_id")


def clean_missing_text(series: pd.Series) -> pd.Series:
    """Trim strings and standardize project-wide missing tokens."""
    return series.astype("string").str.strip().replace(MISSING_TEXT_VALUES)


def normalize_listing_id(series: pd.Series) -> pd.Series:
    """Normalize listing IDs to canonical strings (e.g., 5269.0 -> '5269')."""
    return pd.to_numeric(clean_missing_text(series), errors="coerce").astype("Int64").astype("string")


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
        clean_missing_text(series)
        .str.replace(PRICE_CLEAN_PATTERN, "", regex=True)
        .replace(MISSING_TEXT_VALUES)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_available(series: pd.Series) -> pd.Series:
    normalized = clean_missing_text(series).str.lower()
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


def discover_cities(raw_root: Path, cities_filter: list[str] | None) -> list[tuple[str, str, Path]]:
    """Discover raw calendar files under data/raw/calendars/calendar_<snake>.csv.

    Returns a list of (city_snake, city_label, csv_path) tuples.
    """
    calendars_dir = raw_root / "calendars"
    if not calendars_dir.exists():
        raise FileNotFoundError(
            f"Raw calendars directory not found: {calendars_dir}. "
            "Expected layout: data/raw/calendars/calendar_<snake_city>.csv"
        )

    pairs: list[tuple[str, str, Path]] = []
    for csv_path in sorted(calendars_dir.glob("calendar_*.csv")):
        city_snake = csv_path.stem.removeprefix("calendar_")
        city_label = CITY_LABEL_BY_SNAKE.get(city_snake)
        if not city_label:
            print(f"WARN: unrecognized city snake '{city_snake}' for file {csv_path.name}; skipping")
            continue
        if cities_filter and city_snake not in cities_filter:
            continue
        pairs.append((city_snake, city_label, csv_path))

    if not pairs:
        raise FileNotFoundError(
            f"No calendar_<city>.csv files matched under {calendars_dir} "
            f"for the configured cities {sorted(CITY_LABEL_BY_SNAKE)}."
        )
    return pairs


def update_sum_acc(acc: pd.DataFrame | None, chunk_agg: pd.DataFrame) -> pd.DataFrame:
    if acc is None:
        return chunk_agg
    return acc.add(chunk_agg, fill_value=0)


def update_minmax_acc(acc: pd.DataFrame | None, chunk_agg: pd.DataFrame) -> pd.DataFrame:
    if acc is None:
        return chunk_agg
    combined = pd.concat([acc, chunk_agg])
    return combined.groupby(level=0).agg(
        {
            "min_minimum_nights": "min",
            "max_maximum_nights": "max",
            "first_date": "min",
            "last_date": "max",
        }
    )


def process_city(
    city_snake: str,
    city_label: str,
    csv_file: Path,
    write_row_file: bool,
    write_merged: bool,
    merged_first_write: list[bool],
) -> dict:
    output_row_file = STANDARD_CALENDAR_DIR / city_snake / f"calendar_{city_snake}_cleaned.csv"
    output_listing_file = STANDARD_CALENDAR_DIR / city_snake / f"occupation_{city_snake}_cleaned.csv"
    for path in (output_listing_file,):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
    if write_row_file:
        output_row_file.parent.mkdir(parents=True, exist_ok=True)
        if output_row_file.exists():
            output_row_file.unlink()

    total_size = csv_file.stat().st_size
    rows_in = 0
    rows_out = 0
    duplicate_rows_removed = 0
    missing_required_rows_removed = 0
    invalid_date_rows_removed = 0
    invalid_available_rows_removed = 0
    price_clipped_count = 0
    min_nights_clipped_count = 0
    max_nights_clipped_count = 0
    available_true_rows = 0
    available_false_rows = 0
    price_missing_before = 0
    adjusted_price_missing_before = 0
    price_non_null_after = 0
    adjusted_price_non_null_after = 0

    seen_hashes: set[int] = set()
    sum_acc: pd.DataFrame | None = None
    minmax_acc: pd.DataFrame | None = None

    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = pd.read_csv(handle, usecols=EXPECTED_COLUMNS, chunksize=CHUNK_SIZE)
        for chunk_index, chunk in enumerate(reader):
            rows_in += len(chunk)

            for col in EXPECTED_COLUMNS:
                chunk[col] = clean_missing_text(chunk[col])
            chunk["listing_id"] = normalize_listing_id(chunk["listing_id"])

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
            filtered["available"] = filtered["available"].astype(bool)

            price_missing_before += int(filtered["price"].isna().sum())
            adjusted_price_missing_before += int(filtered["adjusted_price"].isna().sum())

            filtered["price"] = normalize_price(filtered["price"])
            filtered["adjusted_price"] = normalize_price(filtered["adjusted_price"])

            price_clip_mask = filtered["price"].notna() & (filtered["price"] > PRICE_HARD_CAP)
            price_clipped_count += int(price_clip_mask.sum())
            filtered.loc[price_clip_mask, "price"] = pd.NA

            adj_clip_mask = filtered["adjusted_price"].notna() & (filtered["adjusted_price"] > PRICE_HARD_CAP)
            filtered.loc[adj_clip_mask, "adjusted_price"] = pd.NA

            filtered["minimum_nights"] = pd.to_numeric(filtered["minimum_nights"], errors="coerce")
            filtered["maximum_nights"] = pd.to_numeric(filtered["maximum_nights"], errors="coerce")

            min_clip_mask = filtered["minimum_nights"].notna() & (
                (filtered["minimum_nights"] < 1) | (filtered["minimum_nights"] > NIGHTS_HARD_CAP)
            )
            max_clip_mask = filtered["maximum_nights"].notna() & (
                (filtered["maximum_nights"] < 1) | (filtered["maximum_nights"] > NIGHTS_HARD_CAP)
            )
            min_nights_clipped_count += int(min_clip_mask.sum())
            max_nights_clipped_count += int(max_clip_mask.sum())
            filtered["minimum_nights"] = filtered["minimum_nights"].clip(lower=1, upper=NIGHTS_HARD_CAP)
            filtered["maximum_nights"] = filtered["maximum_nights"].clip(lower=1, upper=NIGHTS_HARD_CAP)
            filtered["minimum_nights"] = filtered["minimum_nights"].astype("Int64")
            filtered["maximum_nights"] = filtered["maximum_nights"].astype("Int64")

            filtered["city"] = city_snake

            avail_int = filtered["available"].astype(int)
            unavail_int = 1 - avail_int
            price_avail = filtered["price"].where(filtered["available"])
            price_unavail = filtered["price"].where(~filtered["available"])

            agg_input = pd.DataFrame(
                {
                    "n_days": 1,
                    "n_days_available": avail_int.values,
                    "n_days_unavailable": unavail_int.values,
                    "price_sum_when_available": price_avail.fillna(0).values,
                    "price_count_when_available": price_avail.notna().astype(int).values,
                    "price_sum_when_unavailable": price_unavail.fillna(0).values,
                    "price_count_when_unavailable": price_unavail.notna().astype(int).values,
                },
                index=filtered["listing_id"].values,
            )
            agg_input.index.name = "listing_id"
            chunk_sum = agg_input.groupby(level=0).sum()
            sum_acc = update_sum_acc(sum_acc, chunk_sum)

            minmax_input = pd.DataFrame(
                {
                    "min_minimum_nights": filtered["minimum_nights"].astype("Int64").values,
                    "max_maximum_nights": filtered["maximum_nights"].astype("Int64").values,
                    "first_date": filtered["date"].values,
                    "last_date": filtered["date"].values,
                },
                index=filtered["listing_id"].values,
            )
            minmax_input.index.name = "listing_id"
            chunk_minmax = minmax_input.groupby(level=0).agg(
                {
                    "min_minimum_nights": "min",
                    "max_maximum_nights": "max",
                    "first_date": "min",
                    "last_date": "max",
                }
            )
            minmax_acc = update_minmax_acc(minmax_acc, chunk_minmax)

            available_true_rows += int(avail_int.sum())
            available_false_rows += int(unavail_int.sum())
            price_non_null_after += int(filtered["price"].notna().sum())
            adjusted_price_non_null_after += int(filtered["adjusted_price"].notna().sum())

            rows_out += len(filtered)

            if write_row_file:
                out_chunk = filtered[OUTPUT_ROW_COLUMNS]
                out_chunk.to_csv(
                    output_row_file,
                    mode="w" if chunk_index == 0 else "a",
                    index=False,
                    header=chunk_index == 0,
                    encoding="utf-8-sig",
                    quoting=csv.QUOTE_ALL,
                    quotechar='"',
                    escapechar="\\",
                )

            if write_merged:
                out_chunk = filtered[OUTPUT_ROW_COLUMNS]
                first_write = merged_first_write[0]
                out_chunk.to_csv(
                    ALL_CITIES_ROW_FILE,
                    mode="w" if first_write else "a",
                    index=False,
                    header=first_write,
                    encoding="utf-8-sig",
                    quoting=csv.QUOTE_ALL,
                    quotechar='"',
                    escapechar="\\",
                )
                merged_first_write[0] = False

            try:
                render_progress(f"{city_snake:14}", handle.tell(), total_size)
            except OSError:
                pass

    listings_with_price = 0
    if sum_acc is None or minmax_acc is None:
        listing_table = pd.DataFrame()
    else:
        listing_table = sum_acc.join(minmax_acc, how="outer")
        listing_table.index.name = "listing_id"
        listing_table = listing_table.reset_index()
        listing_table["city"] = city_snake
        n_days = listing_table["n_days"].astype(float)
        listing_table["availability_rate"] = listing_table["n_days_available"] / n_days
        listing_table["unavailability_rate"] = listing_table["n_days_unavailable"] / n_days
        listing_table["occupancy_rate_proxy"] = listing_table["unavailability_rate"]

        prices = load_listing_prices(city_label)
        listing_table = listing_table.merge(prices, on="listing_id", how="left")
        listings_with_price = int(listing_table["listing_price"].notna().sum())

        listing_table["est_annual_revenue_proxy"] = (
            listing_table["listing_price"] * listing_table["occupancy_rate_proxy"] * 365
        )

        listing_columns = [
            "listing_id",
            "city",
            "n_days",
            "first_date",
            "last_date",
            "n_days_available",
            "n_days_unavailable",
            "availability_rate",
            "unavailability_rate",
            "occupancy_rate_proxy",
            "listing_price",
            "min_minimum_nights",
            "max_maximum_nights",
            "est_annual_revenue_proxy",
        ]
        listing_table = listing_table[listing_columns]
        listing_table.to_csv(
            output_listing_file,
            index=False,
            encoding="utf-8-sig",
            quoting=csv.QUOTE_ALL,
            quotechar='"',
            escapechar="\\",
        )

    rows_removed_total = rows_in - rows_out
    percent_removed = 0 if rows_in == 0 else round((rows_removed_total / rows_in) * 100, 2)
    listings_count = len(listing_table) if not listing_table.empty else 0
    avg_occupancy_proxy = (
        round(float(listing_table["occupancy_rate_proxy"].mean()), 4)
        if listings_count > 0
        else None
    )
    median_listing_price = (
        round(float(listing_table["listing_price"].median()), 2)
        if listings_count > 0 and listing_table["listing_price"].notna().any()
        else None
    )
    median_est_revenue = (
        round(float(listing_table["est_annual_revenue_proxy"].median()), 2)
        if listings_count > 0 and listing_table["est_annual_revenue_proxy"].notna().any()
        else None
    )

    return {
        "city": city_snake,
        "city_label": city_label,
        "source_file": str(csv_file.relative_to(PROJECT_ROOT)),
        "row_output_file": str(output_row_file.relative_to(PROJECT_ROOT)) if write_row_file else "",
        "listing_output_file": str(output_listing_file.relative_to(PROJECT_ROOT)),
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_removed_total": rows_removed_total,
        "percent_removed": percent_removed,
        "duplicate_rows_removed": duplicate_rows_removed,
        "missing_required_rows_removed": missing_required_rows_removed,
        "invalid_date_rows_removed": invalid_date_rows_removed,
        "invalid_available_rows_removed": invalid_available_rows_removed,
        "price_clipped_count": price_clipped_count,
        "min_nights_clipped_count": min_nights_clipped_count,
        "max_nights_clipped_count": max_nights_clipped_count,
        "calendar_price_missing_before": price_missing_before,
        "calendar_adjusted_price_missing_before": adjusted_price_missing_before,
        "calendar_price_non_null_after": price_non_null_after,
        "calendar_adjusted_price_non_null_after": adjusted_price_non_null_after,
        "available_true_rows": available_true_rows,
        "available_false_rows": available_false_rows,
        "listings_count": listings_count,
        "listings_with_price": listings_with_price,
        "avg_occupancy_proxy": avg_occupancy_proxy,
        "median_listing_price": median_listing_price,
        "median_est_annual_revenue_proxy": median_est_revenue,
    }


def merge_listing_tables(audit_rows: list[dict]) -> None:
    frames: list[pd.DataFrame] = []
    for row in audit_rows:
        path = PROJECT_ROOT / row["listing_output_file"]
        if path.exists() and path.stat().st_size > 0:
            frames.append(pd.read_csv(path, encoding="utf-8-sig"))
    if not frames:
        return
    merged = pd.concat(frames, ignore_index=True)
    merged.to_csv(
        ALL_CITIES_LISTING_FILE,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_ALL,
        quotechar='"',
        escapechar="\\",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Clean Airbnb calendar files for the MBA706 Term Project across all 5 cities, "
            "produce per-city listing-level occupancy tables, and a merged dataset."
        )
    )
    parser.add_argument(
        "--cities",
        nargs="*",
        choices=sorted(CITY_LABEL_BY_SNAKE.keys()),
        default=None,
        help="Optional subset of cities (snake_case) to process. Defaults to all five.",
    )
    parser.add_argument(
        "--no-merged-rows",
        action="store_true",
        help="Skip writing the giant merged row-level file (calendar_all_cleaned.csv).",
    )
    parser.add_argument(
        "--occupation-only",
        action="store_true",
        help="Only write listing-level occupation outputs; skip per-city and merged row-level calendar CSVs.",
    )
    args = parser.parse_args()

    STANDARD_CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not args.no_merged_rows and ALL_CITIES_ROW_FILE.exists():
        ALL_CITIES_ROW_FILE.unlink()
    if ALL_CITIES_LISTING_FILE.exists():
        ALL_CITIES_LISTING_FILE.unlink()

    pairs = discover_cities(RAW_ROOT, args.cities)
    print(f"Cleaning {len(pairs)} city calendar file(s)")

    audit_rows: list[dict] = []
    merged_first_write = [True]

    for city_snake, city_label, csv_file in pairs:
        print(f"\n=== {city_label} ({city_snake}) -> {csv_file.relative_to(PROJECT_ROOT)} ===")
        result = process_city(
            city_snake,
            city_label,
            csv_file,
            write_row_file=not args.occupation_only,
            write_merged=not args.no_merged_rows and not args.occupation_only,
            merged_first_write=merged_first_write,
        )
        audit_rows.append(result)
        print(
            f"Finished {city_snake}: rows_in={result['rows_in']:,}, "
            f"rows_out={result['rows_out']:,}, removed={result['rows_removed_total']:,}, "
            f"listings={result['listings_count']:,}, "
            f"with_price={result['listings_with_price']:,}, "
            f"avg_occupancy_proxy={result['avg_occupancy_proxy']}, "
            f"median_revenue={result['median_est_annual_revenue_proxy']}"
        )

    merge_listing_tables(audit_rows)

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_ALL,
        quotechar='"',
        escapechar="\\",
    )
    print(f"\nSaved audit summary to {AUDIT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Saved merged occupation table to {ALL_CITIES_LISTING_FILE.relative_to(PROJECT_ROOT)}")
    if not args.no_merged_rows and not args.occupation_only:
        print(f"Saved merged row table to {ALL_CITIES_ROW_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
