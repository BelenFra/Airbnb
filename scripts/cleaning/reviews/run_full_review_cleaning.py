import argparse
import html
import os
import sys
import re
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_USE_SHM"] = "0"
os.environ["MPLCONFIGDIR"] = ".cache/matplotlib"
os.environ["XDG_CACHE_HOME"] = ".cache"
os.environ["MPLBACKEND"] = "Agg"

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR = PROCESSED_ROOT / "review"
REVIEWS_ALL_FILE = PROCESSED_ROOT / "reviews_all_cleaned.csv"
RESULTS_DIR = PROJECT_ROOT / "results" / "reviews"
RANDOM_STATE = 42
MISSING_TEXT_VALUES = {"": pd.NA, "nan": pd.NA, "None": pd.NA}


def city_slug(city_label: str) -> str:
    """Convert 'New York' -> 'new_york' for output filenames."""
    return city_label.strip().lower().replace(" ", "_")

EXPECTED_COLUMNS = ["listing_id", "id", "date", "reviewer_id", "reviewer_name", "comments"]
CHUNK_SIZE = 200_000
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_missing_text(series: pd.Series) -> pd.Series:
    """Trim strings and standardize project-wide missing tokens."""
    return series.astype("string").str.strip().replace(MISSING_TEXT_VALUES)


def clean_comment(text: str) -> str:
    text = html.unescape(str(text))
    text = HTML_TAG_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text.lower()


def hash_rows(df: pd.DataFrame) -> pd.Series:
    return pd.util.hash_pandas_object(df[EXPECTED_COLUMNS], index=False)


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


def process_city(csv_file: Path, city: str, min_length: int) -> dict:
    output_file = PROCESSED_DIR / city / f"reviews_{city}_cleaned.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists():
        output_file.unlink()

    total_size = csv_file.stat().st_size
    seen_hashes = set()

    rows_in = 0
    rows_out = 0
    duplicate_rows_removed = 0
    missing_rows_removed = 0
    blank_after_cleaning = 0
    short_comments_removed = 0
    rows_with_html_tags = 0
    rows_changed_by_text_cleaning = 0
    kept_comment_length_sum = 0

    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        for chunk_index, chunk in enumerate(pd.read_csv(handle, usecols=EXPECTED_COLUMNS, chunksize=CHUNK_SIZE)):
            rows_in += len(chunk)

            for col in EXPECTED_COLUMNS:
                chunk[col] = clean_missing_text(chunk[col])

            row_hashes = hash_rows(chunk)
            duplicate_mask = row_hashes.isin(seen_hashes)
            duplicate_rows_removed += int(duplicate_mask.sum())
            seen_hashes.update(row_hashes[~duplicate_mask].tolist())

            non_missing_mask = chunk.notna().all(axis=1)
            missing_rows_removed += int((~non_missing_mask).sum())

            filtered = chunk.loc[~duplicate_mask & non_missing_mask].copy()

            original_comments = filtered["comments"].astype(str)
            rows_with_html_tags += int(original_comments.str.contains(HTML_TAG_PATTERN, regex=True).sum())

            filtered["comments_clean"] = original_comments.map(clean_comment)
            filtered["comments_clean_length"] = filtered["comments_clean"].str.len()

            rows_changed_by_text_cleaning += int((filtered["comments_clean"] != original_comments.str.strip().str.lower()).sum())

            blank_mask = filtered["comments_clean"].eq("")
            short_mask = filtered["comments_clean_length"] < min_length

            blank_after_cleaning += int(blank_mask.sum())
            short_comments_removed += int((~blank_mask & short_mask).sum())

            final_chunk = filtered.loc[~blank_mask & ~short_mask].copy()
            rows_out += len(final_chunk)
            kept_comment_length_sum += int(final_chunk["comments_clean_length"].sum())

            final_chunk.to_csv(
                output_file,
                mode="w" if chunk_index == 0 else "a",
                index=False,
                header=chunk_index == 0,
                encoding="utf-8-sig",
            )

            try:
                render_progress(f"{city:14}", handle.tell(), total_size)
            except OSError:
                pass

    avg_kept_comment_length = 0 if rows_out == 0 else round(kept_comment_length_sum / rows_out, 2)
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
        "missing_rows_removed": missing_rows_removed,
        "rows_with_html_tags": rows_with_html_tags,
        "rows_changed_by_text_cleaning": rows_changed_by_text_cleaning,
        "blank_after_cleaning": blank_after_cleaning,
        "short_comments_removed": short_comments_removed,
        "min_comment_length": min_length,
        "avg_kept_comment_length": avg_kept_comment_length,
    }


def merge_review_outputs(audit_rows: list[dict]) -> None:
    REVIEWS_ALL_FILE.parent.mkdir(parents=True, exist_ok=True)
    if REVIEWS_ALL_FILE.exists():
        REVIEWS_ALL_FILE.unlink()

    wrote_header = False
    for row in audit_rows:
        output_file = PROJECT_ROOT / row["output_file"]
        if not output_file.exists() or output_file.stat().st_size == 0:
            continue
        for chunk in pd.read_csv(output_file, encoding="utf-8-sig", chunksize=CHUNK_SIZE):
            chunk.to_csv(
                REVIEWS_ALL_FILE,
                mode="a",
                index=False,
                header=not wrote_header,
                encoding="utf-8-sig",
            )
            wrote_header = True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean Airbnb review text into data/processed/review/<city>/ plus reviews_all_cleaned.csv."
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=30,
        help="Minimum number of characters required after text cleaning. Default: 30.",
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    city_dirs = sorted(
        p for p in RAW_DIR.iterdir() if p.is_dir() and (p / "reviews.csv").exists()
    )
    if not city_dirs:
        raise FileNotFoundError(
            f"No <City>/reviews.csv files found under {RAW_DIR}"
        )

    audit_rows = []
    print(
        f"Cleaning {len(city_dirs)} city review files with minimum cleaned comment length = {args.min_length}"
    )
    for city_dir in city_dirs:
        city = city_slug(city_dir.name)
        csv_file = city_dir / "reviews.csv"
        print(f"Starting {city_dir.name} -> {csv_file.relative_to(PROJECT_ROOT)}")
        result = process_city(csv_file, city=city, min_length=args.min_length)
        audit_rows.append(result)
        print(
            f"Finished {result['city']}: rows_in={result['rows_in']}, "
            f"rows_out={result['rows_out']}, removed={result['rows_removed_total']}"
        )

    audit_df = pd.DataFrame(audit_rows)
    audit_path = RESULTS_DIR / "reviews_cleaning_audit.csv"
    audit_df.to_csv(audit_path, index=False, encoding="utf-8-sig")
    merge_review_outputs(audit_rows)
    print(f"Saved audit summary to {audit_path}")
    print(f"Saved merged reviews to {REVIEWS_ALL_FILE}")


if __name__ == "__main__":
    main()
