"""
Full listing-data cleaning pipeline (MBA706 Airbnb Revenue Analytics).

Combines logic from the former standalone scripts listing_by_city_cleaning.py and
listing_replace_nulls.py. Naming mirrors scripts/cleaning/calendars/run_full_calendar_cleaning.py
and scripts/cleaning/reviews/run_full_review_cleaning.py.

Phases (offline)
----------------
merge  Align dtypes using the rules documented in this folder's README, union shared
       columns minus license/calendar_updated, concatenate cities with column City,
       drop rows with missing price, and write an internal pre-null intermediate.

null   Apply LISTING_NULL_ACTIONS (below). The cleaner has no external source of
       null rules; EDA artifacts do not influence cleaning behavior.

Primary outputs
---------------
- data/processed/listing/<city>/listing_<city>_cleaned.csv
- data/processed/listing_all_cleaned.csv
- results/listing/listing_by_city_cleaning_summary.txt

Execution
---------
Run this script directly for listing-only cleaning, or use
scripts/cleaning/run_cleaning_pipeline.py for the standardized project pipeline.
The EDA notebook does not execute cleaning scripts and does not produce inputs
consumed by this script.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_USE_SHM"] = "0"
os.environ["MPLCONFIGDIR"] = ".cache/matplotlib"
os.environ["XDG_CACHE_HOME"] = ".cache"
os.environ["MPLBACKEND"] = "Agg"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from mba706_toolkit import load_data

RANDOM_STATE = 42

# Listing null-handling rules (Prof. Emadi business rule: never impute price).
LISTING_NULL_ACTIONS: Dict[str, str] = {
    "price": "Remove empty",
    "name": "Replace with unknown",
    "scrape_id": "Replace with unknown",
    "description": "Replace with unknown",
    "neighborhood_overview": "Replace with unknown",
    "neighbourhood": "Replace with unknown",
    "neighbourhood_group_cleansed": "Replace with unknown",
    "host_about": "Replace with unknown",
    "host_location": "Replace with unknown",
    "host_name": "Replace with unknown",
    "host_neighbourhood": "Replace with unknown",
    "host_picture_url": "Replace with unknown",
    "host_thumbnail_url": "Replace with unknown",
    "host_response_time": "Replace with unknown",
    "bathrooms_text": "Replace with unknown",
    "has_availability": "Replace with unknown",
    "host_is_superhost": "Replace with unknown",
    "host_response_rate": "Replace with 0",
    "host_acceptance_rate": "Replace with 0",
    "host_listings_count": "Replace with 0",
    "host_total_listings_count": "Replace with 0",
    "estimated_revenue_l365d": "Replace with 0",
    "bedrooms": "Replace with 0",
    "beds": "Replace with 0",
    "bathrooms": "Replace with 0",
    "review_scores_rating": "Replace with 0",
    "review_scores_value": "Replace with 0",
    "review_scores_location": "Replace with 0",
    "review_scores_checkin": "Replace with 0",
    "review_scores_accuracy": "Replace with 0",
    "review_scores_communication": "Replace with 0",
    "review_scores_cleanliness": "Replace with 0",
    "reviews_per_month": "Replace with 0",
    "minimum_minimum_nights": "Replace with 0",
    "maximum_minimum_nights": "Replace with 0",
    "minimum_maximum_nights": "Replace with 0",
    "maximum_maximum_nights": "Replace with 0",
    "first_review": "Replace with 1900-01-01",
    "last_review": "Replace with 1900-01-01",
    "host_since": "Replace with 1900-01-01",
    "host_has_profile_pic": "Replace with f",
    "host_identity_verified": "Replace with f",
    "host_verifications": "Replace with []",
}

LISTING_DROP_COLUMNS = {"license", "calendar_updated"}
PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"
LISTING_ROOT = PROCESSED_ROOT / "listing"
INTERMEDIATE_ROOT = LISTING_ROOT / "_intermediate"
MERGED_BEFORE_NULLS_FILE = INTERMEDIATE_ROOT / "listing_merged_before_nulls.csv"
LISTING_ALL_FILE = PROCESSED_ROOT / "listing_all_cleaned.csv"
LISTING_README = Path(__file__).with_name("README.md")

STRING_COLUMNS = {
    "id",
    "listing_url",
    "scrape_id",
    "source",
    "name",
    "description",
    "neighborhood_overview",
    "picture_url",
    "host_id",
    "host_url",
    "host_name",
    "host_location",
    "host_about",
    "host_response_time",
    "host_thumbnail_url",
    "host_picture_url",
    "host_neighbourhood",
    "host_verifications",
    "host_has_profile_pic",
    "host_identity_verified",
    "neighbourhood",
    "neighbourhood_cleansed",
    "neighbourhood_group_cleansed",
    "property_type",
    "room_type",
    "bathrooms_text",
    "amenities",
    "has_availability",
}

DATE_COLUMNS = {
    "last_scraped",
    "host_since",
    "calendar_last_scraped",
    "first_review",
    "last_review",
}

BOOLEAN_COLUMNS = {
    "host_is_superhost",
    "host_has_profile_pic",
    "host_identity_verified",
    "has_availability",
    "instant_bookable",
}

INTEGER_COLUMNS = {
    "accommodates",
    "bedrooms",
    "beds",
    "minimum_nights",
    "maximum_nights",
    "minimum_minimum_nights",
    "maximum_minimum_nights",
    "minimum_maximum_nights",
    "maximum_maximum_nights",
    "number_of_reviews",
    "number_of_reviews_ltm",
    "number_of_reviews_l30d",
    "calculated_host_listings_count",
    "calculated_host_listings_count_entire_homes",
    "calculated_host_listings_count_private_rooms",
    "calculated_host_listings_count_shared_rooms",
}

FLOAT_COLUMNS = {
    "price",
    "host_response_rate",
    "host_acceptance_rate",
    "host_listings_count",
    "host_total_listings_count",
    "bathrooms",
    "review_scores_rating",
    "review_scores_accuracy",
    "review_scores_cleanliness",
    "review_scores_checkin",
    "review_scores_communication",
    "review_scores_location",
    "review_scores_value",
    "reviews_per_month",
    "estimated_revenue_l365d",
    "minimum_nights_avg_ntm",
    "maximum_nights_avg_ntm",
}


def clean_missing_text(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    return s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})


def coerce_to_dtype(series: pd.Series, dtype_name: str) -> pd.Series:
    dtype_name = str(dtype_name).strip().lower()
    if not dtype_name or dtype_name == "nan":
        return series

    if dtype_name in {"string", "str", "text"}:
        return clean_missing_text(series)

    if dtype_name in {"float", "float64", "double"}:
        cleaned = clean_missing_text(series).str.replace(r"[$,]", "", regex=True)
        return pd.to_numeric(cleaned, errors="coerce").astype("float64")

    if dtype_name in {"int", "int64", "integer"}:
        cleaned = clean_missing_text(series).str.replace(r"[$,]", "", regex=True)
        numeric = pd.to_numeric(cleaned, errors="coerce")
        return numeric.astype("Int64")

    if dtype_name in {"boolean", "bool"}:
        s = clean_missing_text(series).str.lower()
        mapped = s.map(
            {
                "t": True,
                "f": False,
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "yes": True,
                "no": False,
            }
        )
        return mapped.astype("boolean")

    if dtype_name in {"datetime", "date"}:
        return pd.to_datetime(series, errors="coerce")

    return series


def dtype_for_column(column: str) -> str:
    """Return the listing-cleaning dtype rule documented in README.md."""
    if column in BOOLEAN_COLUMNS:
        return "boolean"
    if column in DATE_COLUMNS or column.endswith("_date"):
        return "datetime"
    if column in INTEGER_COLUMNS:
        return "Int64"
    if column in FLOAT_COLUMNS or column.endswith("_rate") or column.endswith("_price"):
        return "float64"
    if column in STRING_COLUMNS:
        return "string"
    return "string"


def city_slug(city_label: str) -> str:
    return city_label.strip().lower().replace(" ", "_")


def apply_replace_action(series: pd.Series, action_value: str) -> pd.Series:
    action = str(action_value).strip()
    if not action.lower().startswith("replace with "):
        return series

    replacement = action[len("Replace with ") :].strip()
    s = clean_missing_text(series)

    if replacement == "1900-01-01":
        dt = pd.to_datetime(series, errors="coerce")
        return dt.fillna(pd.Timestamp("1900-01-01"))

    if replacement == "0":
        num = pd.to_numeric(series, errors="coerce")
        if num.notna().sum() == 0 and s.notna().sum() > 0:
            return s.fillna("0")
        return num.fillna(0)

    if replacement in {"f", "t"}:
        return s.fillna(replacement)

    return s.fillna(replacement)


def build_action_map() -> Dict[str, str]:
    """Return the embedded LISTING_NULL_ACTIONS rules as the only source of truth.

    The cleaner intentionally does not read EDA artifacts: rules live in code,
    documented in scripts/cleaning/listing/README.md, so behavior is reviewable
    via version control rather than a side-channel CSV.
    """
    return dict(LISTING_NULL_ACTIONS)


def run_merge_phase() -> None:
    data_root = PROJECT_ROOT / "data" / "raw"
    results_root = PROJECT_ROOT / "results"
    listing_results_root = results_root / "listing"
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    LISTING_ROOT.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE_ROOT.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    listing_results_root.mkdir(parents=True, exist_ok=True)

    city_dirs = sorted([p for p in data_root.iterdir() if p.is_dir()])
    city_frames: Dict[str, pd.DataFrame] = {}
    initial_obs = 0
    column_sets: list[set] = []

    for city_dir in city_dirs:
        city = city_dir.name
        listings_path = city_dir / "listings.csv"
        if not listings_path.exists():
            continue

        load_result = load_data(str(listings_path), dataset_name=f"{city.lower().replace(' ', '_')}_listings_cleaning")
        if load_result.get("status") != "success":
            raise RuntimeError(f"Failed to load {listings_path}: {load_result}")

        df = pd.read_csv(listings_path, encoding="utf-8-sig")
        initial_obs += len(df)
        column_sets.append(set(df.columns))

        for col in df.columns:
            df[col] = coerce_to_dtype(df[col], dtype_for_column(col))

        city_frames[city] = df

    if not city_frames:
        raise RuntimeError("No city listings.csv files found in data/raw.")

    raw_union_columns = sorted(set.union(*column_sets))
    shared_columns = sorted(set.intersection(*column_sets))
    final_columns = [c for c in shared_columns if c not in LISTING_DROP_COLUMNS]
    non_shared_columns = sorted(set(raw_union_columns) - set(shared_columns))
    explicit_removed_columns = sorted(set(shared_columns) - set(final_columns))
    removed_columns_count = len(non_shared_columns) + len(explicit_removed_columns)

    cleaned_city_frames = []
    for city, df in city_frames.items():
        df_city = df[final_columns].copy()
        df_city["City"] = city
        cleaned_city_frames.append(df_city)

    combined = pd.concat(cleaned_city_frames, ignore_index=True)
    pre_price_filter_obs = len(combined)
    pre_price_filter_cols = len(combined.columns)

    price_series = clean_missing_text(combined["price"])
    combined = combined[price_series.notna()].copy()
    removed_price_null_obs = pre_price_filter_obs - len(combined)

    final_obs = len(combined)
    final_cols = len(combined.columns)

    combined.to_csv(MERGED_BEFORE_NULLS_FILE, index=False, encoding="utf-8-sig")

    summary_txt = listing_results_root / "listing_by_city_cleaning_summary.txt"
    with open(summary_txt, "w", encoding="utf-8") as f:
        f.write("Listing by city cleaning summary\n")
        f.write(f"Initial observations (all city listings combined): {initial_obs}\n")
        f.write(f"Initial columns (raw union across city files): {len(raw_union_columns)}\n")
        f.write(f"Columns removed - non shared across cities: {len(non_shared_columns)}\n")
        f.write(f"Columns removed - explicit (license, calendar_updated): {len(explicit_removed_columns)}\n")
        f.write(f"Observations removed because price is null/empty: {removed_price_null_obs}\n")
        f.write(f"Columns removed: {removed_columns_count}\n")
        f.write(f"Columns after column filtering (before price row filter): {pre_price_filter_cols}\n")
        f.write(f"Final observations: {final_obs}\n")
        f.write(f"Final columns: {final_cols}\n")
        f.write(f"Intermediate output file: {MERGED_BEFORE_NULLS_FILE}\n")
        f.write(f"Dtype rules documented in: {LISTING_README}\n")

    print("Listing merge phase completed.")
    print(f"Saved pre-null intermediate: {MERGED_BEFORE_NULLS_FILE}")
    print(f"Saved summary: {summary_txt}")


def run_null_phase() -> None:
    merged_file = MERGED_BEFORE_NULLS_FILE

    if not merged_file.exists():
        raise FileNotFoundError(f"Merged file not found: {merged_file}. Run --phase merge first.")

    df = pd.read_csv(merged_file, encoding="utf-8-sig", low_memory=False)
    action_map = build_action_map()

    initial_rows = len(df)
    initial_cols = len(df.columns)
    total_cells_null_before = int(df.isna().sum().sum())

    for col, action in action_map.items():
        if col not in df.columns or action == "":
            continue

        if action.lower() == "remove empty":
            before = len(df)
            mask_non_empty = clean_missing_text(df[col]).notna()
            df = df.loc[mask_non_empty].copy()
            continue

        if action.lower().startswith("replace with "):
            df[col] = apply_replace_action(df[col], action)

    final_rows = len(df)
    total_cells_null_after = int(df.isna().sum().sum())

    LISTING_ALL_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(LISTING_ALL_FILE, index=False, encoding="utf-8-sig")

    if "City" not in df.columns:
        raise ValueError("Expected City column in listing data before writing per-city outputs.")
    for city, city_df in df.groupby("City", dropna=False):
        slug = city_slug(str(city))
        output_file = LISTING_ROOT / slug / f"listing_{slug}_cleaned.csv"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        city_df.to_csv(output_file, index=False, encoding="utf-8-sig")

    print("Null replacement phase completed.")
    print(f"Input rows: {initial_rows}; output rows: {final_rows}")
    print(f"Null cells before: {total_cells_null_before}; after: {total_cells_null_after}")
    print(f"Final rows: {final_rows}")
    print(f"Saved: {LISTING_ALL_FILE}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Listing cleaning: merge + null replacement.")
    p.add_argument(
        "--phase",
        choices=("merge", "null", "all"),
        default="all",
        help="Cleaning phase(s) to run.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.phase in ("merge", "all"):
        run_merge_phase()
    if args.phase in ("null", "all"):
        run_null_phase()
    print("Listing cleaning CLI complete.")


if __name__ == "__main__":
    main()
