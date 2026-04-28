"""Calendar cleaning pipeline for the MBA706 Term Project (Yu Wang).

Reads raw Inside Airbnb calendar files from
    data/Term Project/<City Name>/calendar.csv
and produces, in a single streaming pass per city:

* data/processed/calendars/<city>_calendar_cleaned.csv  (per-city, row-level)
* data/processed/calendars/<city>_listing_occupancy.csv (per-city, listing-level)
* data/processed/calendars/all_cities_calendar_cleaned.csv   (merged row-level)
* data/processed/calendars/all_cities_listing_occupancy.csv  (merged listing-level)
* results/calendars/calendars_cleaning_audit.csv             (per-city audit)

Cleaning rules and occupancy definition are documented in
    results/calendars/calendar_cleaning_decisions.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("KMP_USE_SHM", "0")

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_ROOT = PROJECT_ROOT / "data" / "Term Project"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "calendars"
RESULTS_DIR = PROJECT_ROOT / "results" / "calendars"

CITY_NAME_MAP = {
    "Hawaii": "hawaii",
    "Los Angeles": "los_angeles",
    "Nashville": "nashville",
    "New York": "new_york",
    "San Francisco": "san_francisco",
}

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
PRICE_HARD_CAP = 10_000.0
NIGHTS_HARD_CAP = 1125
ALL_CITIES_ROW_FILE = PROCESSED_DIR / "all_cities_calendar_cleaned.csv"
ALL_CITIES_LISTING_FILE = PROCESSED_DIR / "all_cities_listing_occupancy.csv"
AUDIT_FILE = RESULTS_DIR / "calendars_cleaning_audit.csv"


def load_listing_prices(city_dir: Path) -> pd.DataFrame:
    """Read listings.csv from the given city dir and return [listing_id, listing_price].

    Inside Airbnb's calendar dumps no longer carry per-night prices, so the
    nightly price used for revenue estimation must come from listings.csv.
    """
    listings_file = city_dir / "listings.csv"
    if not listings_file.exists():
        return pd.DataFrame(columns=["listing_id", "listing_price"])
    df = pd.read_csv(listings_file, usecols=["id", "price"])
    df = df.rename(columns={"id": "listing_id"})
    df["listing_price"] = (
        df["price"]
        .fillna("")
        .astype(str)
        .str.replace(PRICE_CLEAN_PATTERN, "", regex=True)
        .replace("", pd.NA)
    )
    df["listing_price"] = pd.to_numeric(df["listing_price"], errors="coerce")
    df.loc[df["listing_price"] > PRICE_HARD_CAP, "listing_price"] = pd.NA
    return df[["listing_id", "listing_price"]]


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


def discover_cities(raw_root: Path, cities_filter: list[str] | None) -> list[tuple[str, str, Path]]:
    pairs: list[tuple[str, str, Path]] = []
    if not raw_root.exists():
        raise FileNotFoundError(f"Raw root not found: {raw_root}")
    for city_dir in sorted(raw_root.iterdir()):
        if not city_dir.is_dir():
            continue
        city_snake = CITY_NAME_MAP.get(city_dir.name)
        if not city_snake:
            continue
        csv_path = city_dir / "calendar.csv"
        if not csv_path.exists():
            print(f"WARN: missing {csv_path}")
            continue
        if cities_filter and city_snake not in cities_filter:
            continue
        pairs.append((city_snake, city_dir.name, csv_path))
    if not pairs:
        raise FileNotFoundError(
            f"No calendar.csv files found under {raw_root} for the configured city map."
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
    city_dir: Path,
    write_merged: bool,
    merged_first_write: list[bool],
) -> dict:
    output_row_file = PROCESSED_DIR / f"{city_snake}_calendar_cleaned.csv"
    output_listing_file = PROCESSED_DIR / f"{city_snake}_listing_occupancy.csv"
    for path in (output_row_file, output_listing_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()

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

            out_chunk = filtered[OUTPUT_ROW_COLUMNS]
            rows_out += len(out_chunk)

            out_chunk.to_csv(
                output_row_file,
                mode="w" if chunk_index == 0 else "a",
                index=False,
                header=chunk_index == 0,
            )

            if write_merged:
                first_write = merged_first_write[0]
                out_chunk.to_csv(
                    ALL_CITIES_ROW_FILE,
                    mode="w" if first_write else "a",
                    index=False,
                    header=first_write,
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

        prices = load_listing_prices(city_dir)
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
        listing_table.to_csv(output_listing_file, index=False)

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
        "row_output_file": str(output_row_file.relative_to(PROJECT_ROOT)),
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
            frames.append(pd.read_csv(path))
    if not frames:
        return
    merged = pd.concat(frames, ignore_index=True)
    merged.to_csv(ALL_CITIES_LISTING_FILE, index=False)


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
        choices=sorted(set(CITY_NAME_MAP.values())),
        default=None,
        help="Optional subset of cities (snake_case) to process. Defaults to all five.",
    )
    parser.add_argument(
        "--no-merged-rows",
        action="store_true",
        help="Skip writing the giant merged row-level file (all_cities_calendar_cleaned.csv).",
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
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
        city_dir = csv_file.parent
        print(f"\n=== {city_label} ({city_snake}) -> {csv_file.relative_to(PROJECT_ROOT)} ===")
        result = process_city(
            city_snake,
            city_label,
            csv_file,
            city_dir,
            write_merged=not args.no_merged_rows,
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
    audit_df.to_csv(AUDIT_FILE, index=False)
    print(f"\nSaved audit summary to {AUDIT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Saved merged listing table to {ALL_CITIES_LISTING_FILE.relative_to(PROJECT_ROOT)}")
    if not args.no_merged_rows:
        print(f"Saved merged row table to {ALL_CITIES_ROW_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
