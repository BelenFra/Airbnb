"""
Compare current data/processed outputs against data/processed/Previous.

The script writes:
- results/processed_comparison_summary.csv
- results/processed_comparison_details.txt

It is designed for large CSV files: exact equality is checked with streaming
SHA-256 hashes, and detailed profiles are only computed for changed CSV pairs
unless --profile-all is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_USE_SHM"] = "0"
os.environ["MPLCONFIGDIR"] = ".cache/matplotlib"
os.environ["XDG_CACHE_HOME"] = ".cache"
os.environ["MPLBACKEND"] = "Agg"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"
PREVIOUS_ROOT = PROCESSED_ROOT / "Previous"
RESULTS_DIR = PROJECT_ROOT / "results"
SUMMARY_FILE = RESULTS_DIR / "processed_comparison_summary.csv"
DETAIL_FILE = RESULTS_DIR / "processed_comparison_details.txt"
CHUNK_SIZE = 200_000


def rel_files(root: Path) -> set[Path]:
    files: set[Path] = set()
    if not root.exists():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if root == PROCESSED_ROOT and PREVIOUS_ROOT in path.parents:
            continue
        if path.name == ".gitkeep":
            continue
        files.add(path.relative_to(root))
    return files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def csv_profile(path: Path) -> dict[str, Any]:
    rows = 0
    null_counts: Counter[str] = Counter()
    dtype_names: dict[str, str] = {}
    unique_counts: dict[str, int] = {}

    for chunk_index, chunk in enumerate(pd.read_csv(path, encoding="utf-8-sig", chunksize=CHUNK_SIZE, low_memory=False)):
        rows += len(chunk)
        null_counts.update(chunk.isna().sum().to_dict())
        if chunk_index == 0:
            dtype_names = {col: str(dtype) for col, dtype in chunk.dtypes.items()}
            for col in chunk.columns[:20]:
                unique_counts[col] = int(chunk[col].nunique(dropna=True))

    return {
        "rows": rows,
        "columns": read_header(path),
        "null_counts": dict(null_counts),
        "dtypes": dtype_names,
        "unique_counts_first_20_columns": unique_counts,
    }


def compare_profiles(current_profile: dict[str, Any], previous_profile: dict[str, Any]) -> list[str]:
    notes: list[str] = []

    current_cols = current_profile["columns"]
    previous_cols = previous_profile["columns"]
    added_cols = [col for col in current_cols if col not in previous_cols]
    removed_cols = [col for col in previous_cols if col not in current_cols]
    if added_cols:
        notes.append(f"added_columns={added_cols}")
    if removed_cols:
        notes.append(f"removed_columns={removed_cols}")
    if current_cols != previous_cols and not added_cols and not removed_cols:
        notes.append("column_order_changed")

    dtype_changes = {
        col: (previous_profile["dtypes"].get(col), current_profile["dtypes"].get(col))
        for col in current_cols
        if col in previous_cols and previous_profile["dtypes"].get(col) != current_profile["dtypes"].get(col)
    }
    if dtype_changes:
        notes.append(f"dtype_changes={dtype_changes}")

    null_changes = {}
    for col in current_cols:
        if col not in previous_cols:
            continue
        current_nulls = current_profile["null_counts"].get(col, 0)
        previous_nulls = previous_profile["null_counts"].get(col, 0)
        if current_nulls != previous_nulls:
            null_changes[col] = previous_nulls, current_nulls
    if null_changes:
        notes.append(f"null_count_changes={null_changes}")

    return notes


def compare_pair(rel_path: Path, profile_all: bool) -> dict[str, Any]:
    current_path = PROCESSED_ROOT / rel_path
    previous_path = PREVIOUS_ROOT / rel_path
    row: dict[str, Any] = {
        "relative_path": rel_path.as_posix(),
        "current_exists": current_path.exists(),
        "previous_exists": previous_path.exists(),
        "current_size_bytes": current_path.stat().st_size if current_path.exists() else None,
        "previous_size_bytes": previous_path.stat().st_size if previous_path.exists() else None,
        "status": "",
        "row_count_previous": None,
        "row_count_current": None,
        "column_count_previous": None,
        "column_count_current": None,
        "important_notes": "",
    }

    if not current_path.exists():
        row["status"] = "missing_current"
        return row
    if not previous_path.exists():
        row["status"] = "new_current"
        return row

    if current_path.suffix.lower() != ".csv" or previous_path.suffix.lower() != ".csv":
        row["status"] = "same_size_non_csv" if row["current_size_bytes"] == row["previous_size_bytes"] else "changed_non_csv"
        return row

    current_header = read_header(current_path)
    previous_header = read_header(previous_path)
    row["column_count_current"] = len(current_header)
    row["column_count_previous"] = len(previous_header)

    current_hash = sha256_file(current_path)
    previous_hash = sha256_file(previous_path)
    if current_hash == previous_hash:
        row["status"] = "identical"
        row["important_notes"] = "byte-for-byte identical"
        return row

    row["status"] = "changed"
    if current_header != previous_header:
        added_cols = [col for col in current_header if col not in previous_header]
        removed_cols = [col for col in previous_header if col not in current_header]
        row["important_notes"] = f"schema differs; added={added_cols}; removed={removed_cols}"

    if profile_all or row["status"] == "changed":
        previous_profile = csv_profile(previous_path)
        current_profile = csv_profile(current_path)
        row["row_count_previous"] = previous_profile["rows"]
        row["row_count_current"] = current_profile["rows"]
        notes = compare_profiles(current_profile, previous_profile)
        if notes:
            row["important_notes"] = "; ".join([note for note in [row["important_notes"], *notes] if note])
        elif not row["important_notes"]:
            row["important_notes"] = "content changed but row counts, columns, dtypes, and null counts match"

    return row


def write_details(summary: pd.DataFrame) -> None:
    lines = [
        "Processed Output Comparison",
        "===========================",
        "",
        f"Current root: {PROCESSED_ROOT}",
        f"Previous root: {PREVIOUS_ROOT}",
        "",
        "Status counts:",
        summary["status"].value_counts(dropna=False).to_string(),
        "",
    ]

    changed = summary.loc[summary["status"].ne("identical")].copy()
    if changed.empty:
        lines.append("No differences found. All matched files are byte-for-byte identical.")
    else:
        lines.append("Important differences:")
        for _, row in changed.iterrows():
            lines.append(
                "- "
                f"{row['relative_path']}: {row['status']}; "
                f"size previous={row['previous_size_bytes']}, current={row['current_size_bytes']}; "
                f"rows previous={row['row_count_previous']}, current={row['row_count_current']}; "
                f"{row['important_notes']}"
            )

    DETAIL_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare current processed outputs against data/processed/Previous.")
    parser.add_argument(
        "--profile-all",
        action="store_true",
        help="Compute full row/null profiles for all CSV pairs, including byte-identical files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not PREVIOUS_ROOT.exists():
        raise FileNotFoundError(f"Missing comparison baseline: {PREVIOUS_ROOT}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    relative_paths = sorted(rel_files(PROCESSED_ROOT) | rel_files(PREVIOUS_ROOT))
    rows = [compare_pair(rel_path, profile_all=args.profile_all) for rel_path in relative_paths]
    summary = pd.DataFrame(rows)
    summary.to_csv(SUMMARY_FILE, index=False, encoding="utf-8-sig")
    write_details(summary)

    print(f"Compared {len(summary)} files.")
    print(summary["status"].value_counts(dropna=False).to_string())
    print(f"Saved summary: {SUMMARY_FILE}")
    print(f"Saved details: {DETAIL_FILE}")


if __name__ == "__main__":
    main()
