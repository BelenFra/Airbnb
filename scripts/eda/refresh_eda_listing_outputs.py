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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mba706_toolkit import load_data, load_excel_data
from matplotlib.patches import Patch


def normalize_city(name: str) -> str:
    """Normalise a city label to snake_case lowercase.

    Accepts inputs like ``"San Francisco"``, ``"san-francisco"``, ``"SanFrancisco"``,
    or ``"san_francisco"`` and returns ``"san_francisco"``.
    """
    name = name.strip().lower()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name


def discover_listings_files(data_root: Path) -> list[tuple[Path, str]]:
    """Find listings CSVs under ``data_root`` regardless of layout.

    Two layouts are supported (in this order):

    1. **Flat per-city files**: ``data_root/listings_<city>.csv`` (case-insensitive
       on the ``listings_`` prefix; ``<city>`` may use spaces, hyphens or
       underscores and is normalised).
    2. **One folder per city**: ``data_root/<City>/listings.csv``.

    Returns a list of ``(file_path, normalised_city)`` tuples sorted by city.
    """
    pairs: list[tuple[Path, str]] = []

    if not data_root.exists():
        return pairs

    # Layout 1: flat files. Match ``listings_*.csv`` case-insensitively.
    pattern = re.compile(r"^listings[_\-\s]+(.+)$", re.IGNORECASE)
    for path in data_root.iterdir():
        if not path.is_file() or path.suffix.lower() != ".csv":
            continue
        m = pattern.match(path.stem)
        if not m:
            continue
        pairs.append((path, normalize_city(m.group(1))))

    if pairs:
        return sorted(pairs, key=lambda t: t[1])

    # Layout 2: one subdirectory per city, with ``listings.csv`` inside.
    for sub in data_root.iterdir():
        if not sub.is_dir():
            continue
        listings = sub / "listings.csv"
        if listings.exists():
            pairs.append((listings, normalize_city(sub.name)))

    return sorted(pairs, key=lambda t: t[1])


def clean_missing(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    return s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})


def suggest_dtype(column: str, observed_dtypes: list[str]) -> str:
    c = column.lower()
    dset = {d for d in observed_dtypes if d and str(d).lower() != "nan"}
    if c in {"instant_bookable", "host_has_profile_pic", "host_is_superhost", "host_identity_verified"}:
        return "boolean"
    if c == "host_response_time":
        return "float"
    if c == "id" or c.endswith("_id"):
        return "float"
    if "date" in c or c.endswith("_since") or c in {"first_review", "last_review", "last_scraped", "calendar_last_scraped"}:
        return "datetime"
    if dset.issubset({"int64"}):
        return "Int64"
    if dset.issubset({"float64"}) or dset.issubset({"int64", "float64"}):
        return "float"
    if any(tok in c for tok in ["price", "rate", "score", "count", "nights", "reviews_per_month", "occupancy", "revenue"]):
        return "float"
    return "string"


def dtype_group(dtype_str: str) -> str:
    d = str(dtype_str).lower()
    if "int" in d or "float" in d or "double" in d:
        return "numeric"
    if "datetime" in d or "date" in d:
        return "date"
    if "bool" in d:
        return "boolean"
    return "text"


def main() -> None:
    data_root = PROJECT_ROOT / "data" / "raw" / "listing"
    results_root = PROJECT_ROOT / "results"
    figures_root = PROJECT_ROOT / "reports" / "figures" / "market_analysis" / "listing"
    results_root.mkdir(parents=True, exist_ok=True)
    figures_root.mkdir(parents=True, exist_ok=True)

    # Load dictionary if available (kept in sync with the notebook). The dictionary
    # file is optional — the rest of the EDA refresh works without it.
    dictionary_file = PROJECT_ROOT / "data" / "raw" / "Inside Airbnb Data Dictionary.xlsx"
    if dictionary_file.exists():
        load_excel_data(
            str(dictionary_file),
            sheet_name="listings.csv detail v4.7",
            dataset_name="dict_listings_refresh",
        )
    else:
        print(f"  (skipping dictionary load: {dictionary_file} not found)")

    # Discover listings files defensively — supports both layouts:
    #   data/raw/listing/listings_<city>.csv   (current)
    #   data/raw/listing/<City>/listings.csv   (legacy)
    # City labels are normalised to snake_case so downstream paths are stable.
    discovered = discover_listings_files(data_root)
    if not discovered:
        raise FileNotFoundError(
            f"No listings CSVs found in {data_root}. Expected either "
            f"'listings_<city>.csv' or '<city>/listings.csv'."
        )
    city_names = [city for _, city in discovered]
    print(f"  Discovered {len(discovered)} listings files: {city_names}")

    all_city_dtypes = {}
    all_city_null_pct = {}
    all_city_row_counts = {}
    all_columns_union = set()

    for listings_file, city in discovered:
        load_data(str(listings_file), dataset_name=f"{city}_listings_refresh")
        df = pd.read_csv(listings_file, encoding="utf-8-sig")

        all_city_row_counts[city] = len(df)
        all_columns_union.update(df.columns)
        all_city_dtypes[city] = {c: str(df[c].dtype) for c in df.columns}

        null_pct_map = {}
        for c in df.columns:
            null_pct_map[c] = (clean_missing(df[c]).isna().sum() / len(df)) * 100 if len(df) else 0.0
        all_city_null_pct[city] = null_pct_map

        # Overwrite null plots (>1%) for each city.
        null_df = pd.DataFrame({"column": list(null_pct_map.keys()), "null_pct": list(null_pct_map.values())})
        null_df = null_df[null_df["null_pct"] > 1.0].sort_values("null_pct", ascending=False)
        if len(null_df) == 0:
            continue

        # Assign color by dtype group.
        color_map = {
            "numeric": "#1f77b4",
            "text": "#ff7f0e",
            "date": "#2ca02c",
            "boolean": "#9467bd",
        }
        dtype_map = all_city_dtypes[city]
        null_df["dtype_group"] = null_df["column"].map(lambda c: dtype_group(dtype_map.get(c, "str")))
        colors = null_df["dtype_group"].map(color_map).tolist()

        plt.figure(figsize=(12, max(6, min(22, 0.35 * len(null_df)))))
        bars = plt.barh(null_df["column"], null_df["null_pct"], color=colors)
        plt.gca().invert_yaxis()
        plt.xlabel("% nulls")
        plt.ylabel("Column")
        city_title = city.replace("_", " ").title()
        plt.title(f"{city_title} - listings.csv null % by column (>1%)")

        # Add null percentage label to each bar.
        for bar, value in zip(bars, null_df["null_pct"]):
            plt.text(
                bar.get_width() + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.1f}%",
                va="center",
                fontsize=8,
            )

        # Add legend for dtype colors.
        legend_handles = [
            Patch(facecolor=color_map["numeric"], label="numeric"),
            Patch(facecolor=color_map["text"], label="text"),
            Patch(facecolor=color_map["date"], label="date"),
            Patch(facecolor=color_map["boolean"], label="boolean"),
        ]
        plt.legend(handles=legend_handles, title="dtype", loc="lower right")
        plt.tight_layout()
        out_plot = figures_root / f"eda_listing_nulls_{city}.png"
        plt.savefig(out_plot, dpi=150)
        plt.close()

    # Rebuild suggested dtype output based on new raw data
    all_columns = sorted(all_columns_union)
    dtype_rows = []
    for c in all_columns:
        row = {"column": c}
        observed = []
        for city in city_names:
            dt = all_city_dtypes.get(city, {}).get(c, "")
            row[city] = dt
            if dt:
                observed.append(dt)
        row["suggested_standardized_dtype"] = suggest_dtype(c, observed)
        dtype_rows.append(row)

    dtype_matrix_df = pd.DataFrame(dtype_rows)
    suggested_dtype_out = dtype_matrix_df[["column", "suggested_standardized_dtype"]].copy()
    suggested_dtype_out.to_csv(results_root / "suggested_dtypes_listing.csv", index=False, encoding="utf-8-sig")

    # Optional: refresh global null report used in section 4b
    total_rows_all = sum(all_city_row_counts.values())
    global_rows = []
    for c in all_columns:
        missing_total = 0.0
        for city in city_names:
            city_rows = all_city_row_counts.get(city, 0)
            city_null_pct = all_city_null_pct.get(city, {}).get(c, 100.0)
            missing_total += (city_null_pct / 100.0) * city_rows
        global_null_pct = (missing_total / total_rows_all) * 100 if total_rows_all else np.nan
        global_rows.append({"column": c, "global_null_pct": round(global_null_pct, 4)})
    pd.DataFrame(global_rows).to_csv(results_root / "listing_global_null_pct.csv", index=False, encoding="utf-8-sig")

    print(f"Cities processed: {city_names}")
    print(f"Plots overwritten in: {figures_root}")
    print(f"Saved: {results_root / 'suggested_dtypes_listing.csv'}")
    print(f"Saved: {results_root / 'listing_global_null_pct.csv'}")


if __name__ == "__main__":
    main()
