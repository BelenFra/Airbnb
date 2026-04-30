"""
Run the Airbnb cleaning pipeline and standardize processed outputs.

Order:
1. Clean listings, then write:
   - data/processed/listing/<city>/listing_<city>_cleaned.csv
   - data/processed/listing_all_cleaned.csv

2. Clean reviews, then write:
   - data/processed/review/<city>/reviews_<city>_cleaned.csv
   - data/processed/reviews_all_cleaned.csv

3. Clean calendars into occupation outputs, using listing_all_cleaned as input:
   - data/processed/calendar/<city>/occupation_<city>_cleaned.csv
   - data/processed/occupation_all_cleaned.csv

4. Join listing_all_cleaned with occupation_all_cleaned:
   - data/processed/master_data.csv
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_USE_SHM"] = "0"
os.environ["MPLCONFIGDIR"] = ".cache/matplotlib"
os.environ["XDG_CACHE_HOME"] = ".cache"
os.environ["MPLBACKEND"] = "Agg"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

RANDOM_STATE = 42

CITIES = ["Hawaii", "Los Angeles", "Nashville", "New York", "San Francisco"]
CITY_SLUGS = {
    "Hawaii": "hawaii",
    "Los Angeles": "los_angeles",
    "Nashville": "nashville",
    "New York": "new_york",
    "San Francisco": "san_francisco",
}

PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"
LISTING_ALL = PROCESSED_ROOT / "listing_all_cleaned.csv"
REVIEWS_ALL = PROCESSED_ROOT / "reviews_all_cleaned.csv"
OCCUPATION_ALL = PROCESSED_ROOT / "occupation_all_cleaned.csv"
MASTER_DATA = PROCESSED_ROOT / "master_data.csv"

LISTING_SUMMARY = PROJECT_ROOT / "results" / "listing" / "listing_by_city_cleaning_summary.txt"
CALENDAR_AUDIT = PROJECT_ROOT / "results" / "calendars" / "calendars_cleaning_audit.csv"
REVIEWS_AUDIT = PROJECT_ROOT / "results" / "reviews" / "reviews_cleaning_audit.csv"

RATE_COLUMNS = ["availability_rate", "unavailability_rate", "occupancy_rate_proxy"]


def run_step(name: str, command: list[str]) -> None:
    print(f"\n=== {name} ===")
    print(" ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    if path.is_file() and path.stat().st_size == 0:
        raise ValueError(f"Empty {label}: {path}")


def normalize_listing_id(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.strip(), errors="coerce").astype("Int64").astype("string")


def assert_no_duplicate_ids(df: pd.DataFrame, column: str, label: str) -> None:
    duplicated = df[column].dropna().duplicated()
    duplicate_count = int(duplicated.sum())
    if duplicate_count:
        examples = df.loc[df[column].duplicated(keep=False), column].dropna().astype(str).head(10).tolist()
        raise ValueError(f"{label} has {duplicate_count} duplicate {column} values. Examples: {examples}")


def validate_occupation_outputs() -> None:
    occupation_files: list[Path] = []
    for _, slug in CITY_SLUGS.items():
        output_file = PROCESSED_ROOT / "calendar" / slug / f"occupation_{slug}_cleaned.csv"
        require_file(output_file, f"{slug} occupation output")
        occupation_df = pd.read_csv(output_file, encoding="utf-8-sig", usecols=["listing_id", "city", *RATE_COLUMNS])
        occupation_df["listing_id"] = normalize_listing_id(occupation_df["listing_id"])
        assert_no_duplicate_ids(occupation_df, "listing_id", f"occupation_{slug}_cleaned")
        bad_city = set(occupation_df["city"].dropna().astype(str).unique()) - {slug}
        if bad_city:
            raise ValueError(f"{output_file} has unexpected city values: {sorted(bad_city)}")
        occupation_files.append(output_file)

    require_file(OCCUPATION_ALL, "merged occupation output")
    occupation_all = pd.read_csv(OCCUPATION_ALL, encoding="utf-8-sig", usecols=["listing_id", "city", *RATE_COLUMNS])
    occupation_all["listing_id"] = normalize_listing_id(occupation_all["listing_id"])
    assert_no_duplicate_ids(occupation_all, "listing_id", "occupation_all_cleaned")


def build_listing_occupation_join() -> None:
    require_file(LISTING_ALL, "listing_all_cleaned")
    require_file(OCCUPATION_ALL, "occupation_all_cleaned")

    listing_df = pd.read_csv(LISTING_ALL, encoding="utf-8-sig", low_memory=False)
    occupation_df = pd.read_csv(
        OCCUPATION_ALL,
        encoding="utf-8-sig",
        usecols=["listing_id", *RATE_COLUMNS],
        low_memory=False,
    )

    listing_df["id"] = normalize_listing_id(listing_df["id"])
    occupation_df["listing_id"] = normalize_listing_id(occupation_df["listing_id"])
    assert_no_duplicate_ids(listing_df, "id", "listing_all_cleaned")
    assert_no_duplicate_ids(occupation_df, "listing_id", "occupation_all_cleaned")

    joined = listing_df.merge(
        occupation_df[["listing_id", *RATE_COLUMNS]],
        left_on="id",
        right_on="listing_id",
        how="left",
        validate="one_to_one",
    )
    joined = joined.drop(columns=["listing_id"])
    joined.to_csv(MASTER_DATA, index=False, encoding="utf-8-sig")


def validate_listing_outputs() -> None:
    require_file(LISTING_ALL, "listing_all_cleaned")
    require_file(LISTING_SUMMARY, "listing merge summary")

    listing_sample = pd.read_csv(LISTING_ALL, usecols=["id", "price", "accommodates", "City"], encoding="utf-8-sig")
    if listing_sample[["id", "price", "City"]].isna().any().any():
        raise ValueError("listing_all_cleaned contains null id, price, or City values")
    if not pd.api.types.is_integer_dtype(listing_sample["accommodates"]):
        raise TypeError("listing_all_cleaned accommodates is not integer typed")
    unknown_cities = set(listing_sample["City"].dropna().unique()) - set(CITIES)
    if unknown_cities:
        raise ValueError(f"Unexpected City values in listing_all_cleaned: {sorted(unknown_cities)}")
    assert_no_duplicate_ids(listing_sample.assign(id=normalize_listing_id(listing_sample["id"])), "id", "listing_all_cleaned")


def validate_review_outputs(require_outputs: bool) -> None:
    if require_outputs:
        require_file(REVIEWS_AUDIT, "reviews audit")
        require_file(REVIEWS_ALL, "reviews_all_cleaned")

    if REVIEWS_AUDIT.exists():
        audit = pd.read_csv(REVIEWS_AUDIT, encoding="utf-8-sig")
        expected_cols = {"city", "output_file", "rows_in", "rows_out", "min_comment_length"}
        missing = expected_cols - set(audit.columns)
        if missing:
            raise ValueError(f"Review audit missing columns: {sorted(missing)}")

    for _, slug in CITY_SLUGS.items():
        review_file = PROCESSED_ROOT / "review" / slug / f"reviews_{slug}_cleaned.csv"
        if require_outputs:
            require_file(review_file, f"{slug} standardized reviews")
        if review_file.exists():
            sample = pd.read_csv(review_file, encoding="utf-8-sig", nrows=10_000)
            required_cols = {"listing_id", "id", "date", "reviewer_id", "reviewer_name", "comments", "comments_clean"}
            missing = required_cols - set(sample.columns)
            if missing:
                raise ValueError(f"{review_file} missing columns: {sorted(missing)}")
            if sample[list(required_cols)].isna().any().any():
                raise ValueError(f"{review_file} sample contains nulls in required columns")


def validate_outputs(require_calendar: bool, require_reviews: bool) -> None:
    print("\n=== Validate standardized outputs ===")
    validate_listing_outputs()
    validate_review_outputs(require_outputs=require_reviews)
    if require_calendar:
        require_file(CALENDAR_AUDIT, "calendar audit")
        validate_occupation_outputs()
        require_file(MASTER_DATA, "master_data output")
    print("Validation passed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cleaning scripts and standardize processed outputs.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing standardized outputs.")
    parser.add_argument("--skip-listing", action="store_true", help="Skip listing cleaning.")
    parser.add_argument("--skip-reviews", action="store_true", help="Skip review cleaning.")
    parser.add_argument("--skip-calendars", action="store_true", help="Skip calendar/occupation cleaning.")
    parser.add_argument(
        "--calendar-write-row-files",
        action="store_true",
        help="Also write large row-level calendar files. By default the pipeline writes occupation outputs only.",
    )
    parser.add_argument("--reviews-min-length", type=int, default=30, help="Minimum cleaned review length.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.validate_only:
        validate_outputs(require_calendar=True, require_reviews=True)
        return

    if not args.skip_listing:
        run_step("Clean listings", [sys.executable, "scripts/cleaning/listing/run_full_listing_cleaning.py", "--phase", "all"])
        validate_listing_outputs()
    else:
        require_file(LISTING_ALL, "listing_all_cleaned")

    if not args.skip_reviews:
        run_step(
            "Clean reviews",
            [
                sys.executable,
                "scripts/cleaning/reviews/run_full_review_cleaning.py",
                "--min-length",
                str(args.reviews_min_length),
            ],
        )
        validate_review_outputs(require_outputs=True)

    if not args.skip_calendars:
        require_file(LISTING_ALL, "listing_all_cleaned required before calendar cleaning")
        command = [sys.executable, "scripts/cleaning/calendars/run_full_calendar_cleaning.py"]
        if not args.calendar_write_row_files:
            command.append("--occupation-only")
        run_step("Clean calendars into occupation outputs", command)
        validate_occupation_outputs()
        build_listing_occupation_join()

    validate_outputs(require_calendar=not args.skip_calendars, require_reviews=not args.skip_reviews)
    print("\nCleaning pipeline complete.")


if __name__ == "__main__":
    main()
