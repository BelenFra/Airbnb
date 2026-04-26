import os
import sys
from pathlib import Path

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


def main() -> None:
    data_root = PROJECT_ROOT / "data" / "raw"
    processed_root = PROJECT_ROOT / "data" / "processed"
    listing_processed_root = processed_root / "listing"
    results_root = PROJECT_ROOT / "results"
    processed_root.mkdir(parents=True, exist_ok=True)
    listing_processed_root.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)

    dtype_file = PROJECT_ROOT / "results" / "suggested_dtypes_listing.csv"
    if not dtype_file.exists():
        raise FileNotFoundError(f"Missing suggested dtypes file: {dtype_file}")

    dtype_map_df = pd.read_csv(dtype_file, encoding="utf-8-sig")
    if "column" not in dtype_map_df.columns or "suggested_standardized_dtype" not in dtype_map_df.columns:
        raise ValueError("Expected columns: column, suggested_standardized_dtype")
    dtype_map = dict(zip(dtype_map_df["column"], dtype_map_df["suggested_standardized_dtype"]))

    city_dirs = sorted([p for p in data_root.iterdir() if p.is_dir()])
    city_frames = {}
    initial_obs = 0
    column_sets = []

    # Load city listings and standardize dtypes per suggested mapping.
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
            suggested = dtype_map.get(col, "")
            df[col] = coerce_to_dtype(df[col], suggested)

        city_frames[city] = df

    if not city_frames:
        raise RuntimeError("No city listings.csv files found in data/raw.")

    # Determine column sets before and after pruning.
    raw_union_columns = sorted(set.union(*column_sets))
    shared_columns = sorted(set.intersection(*column_sets))

    # Remove explicit high-null columns requested.
    drop_explicit = {"license", "calendar_updated"}
    final_columns = [c for c in shared_columns if c not in drop_explicit]
    non_shared_columns = sorted(set(raw_union_columns) - set(shared_columns))
    explicit_removed_columns = sorted(set(shared_columns) - set(final_columns))
    removed_columns_count = len(non_shared_columns) + len(explicit_removed_columns)

    # Keep only final columns, add City, and append all cities.
    cleaned_city_frames = []
    for city, df in city_frames.items():
        df_city = df[final_columns].copy()
        df_city["City"] = city
        cleaned_city_frames.append(df_city)

    combined = pd.concat(cleaned_city_frames, ignore_index=True)
    pre_price_filter_obs = len(combined)
    pre_price_filter_cols = len(combined.columns)

    # Remove rows with null/empty price.
    price_series = clean_missing_text(combined["price"])
    combined = combined[price_series.notna()].copy()
    removed_price_null_obs = pre_price_filter_obs - len(combined)

    final_obs = len(combined)
    final_cols = len(combined.columns)

    # Save outputs.
    out_csv = listing_processed_root / "listing_by_city_cleaned.csv"
    combined.to_csv(out_csv, index=False, encoding="utf-8-sig")

    summary_txt = results_root / "listing_by_city_cleaning_summary.txt"
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
        f.write(f"Output file: {out_csv}\n")

    print("Listing by city cleaning completed.")
    print(f"Initial observations (all city listings combined): {initial_obs}")
    print(f"Initial columns (raw union across city files): {len(raw_union_columns)}")
    print(f"Columns removed - non shared across cities: {len(non_shared_columns)}")
    print(f"Columns removed - explicit (license, calendar_updated): {len(explicit_removed_columns)}")
    print(f"Observations removed because price is null/empty: {removed_price_null_obs}")
    print(f"Columns removed: {removed_columns_count}")
    print(f"Columns after column filtering (before price row filter): {pre_price_filter_cols}")
    print(f"Final observations: {final_obs}")
    print(f"Final columns: {final_cols}")
    print(f"Saved cleaned dataset: {out_csv}")
    print(f"Saved summary: {summary_txt}")


if __name__ == "__main__":
    main()
