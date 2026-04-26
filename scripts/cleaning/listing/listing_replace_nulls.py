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


def clean_missing_text(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    return s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})


def apply_replace_action(series: pd.Series, action_value: str) -> pd.Series:
    """
    Apply actions of the form:
    - Replace with unknown
    - Replace with 0
    - Replace with 1900-01-01
    - Replace with f
    - Replace with []
    """
    action = str(action_value).strip()
    if not action.lower().startswith("replace with "):
        return series

    replacement = action[len("Replace with ") :].strip()

    # Text cleanup first so empty strings are treated as nulls.
    s = clean_missing_text(series)

    # Date replacement.
    if replacement == "1900-01-01":
        dt = pd.to_datetime(series, errors="coerce")
        dt = dt.fillna(pd.Timestamp("1900-01-01"))
        return dt

    # Numeric replacement.
    if replacement == "0":
        num = pd.to_numeric(series, errors="coerce")
        # If numeric conversion fails for many values, fallback to string fill.
        if num.notna().sum() == 0 and s.notna().sum() > 0:
            return s.fillna("0")
        return num.fillna(0)

    # Boolean-like replacement for t/f style columns.
    if replacement in {"f", "t"}:
        return s.fillna(replacement)

    # General string replacement (unknown, [], etc).
    return s.fillna(replacement)


def main() -> None:
    merged_file = PROJECT_ROOT / "data" / "processed" / "listing" / "merged" / "listing_by_city_cleaned.csv"
    actions_file = PROJECT_ROOT / "results" / "listing_global_null_pct.csv"
    out_file = PROJECT_ROOT / "data" / "processed" / "listing" / "merged" / "listing_by_city_cleaned_nulls_replaced.csv"
    summary_file = PROJECT_ROOT / "results" / "listing_replace_nulls_summary.txt"

    if not merged_file.exists():
        raise FileNotFoundError(f"Merged file not found: {merged_file}")
    if not actions_file.exists():
        raise FileNotFoundError(f"Actions file not found: {actions_file}")

    df = pd.read_csv(merged_file, encoding="utf-8-sig", low_memory=False)
    actions_df = pd.read_csv(actions_file, encoding="utf-8-sig")

    required_cols = {"column", "Action"}
    if not required_cols.issubset(actions_df.columns):
        raise ValueError("Actions file must contain columns: column, Action")

    initial_rows = len(df)
    initial_cols = len(df.columns)
    total_cells_null_before = int(df.isna().sum().sum())

    action_map = {
        str(r["column"]).strip(): ("" if pd.isna(r["Action"]) else str(r["Action"]).strip())
        for _, r in actions_df.iterrows()
    }

    rows_removed = 0
    columns_touched = 0
    action_log = []

    for col, action in action_map.items():
        if col not in df.columns or action == "":
            continue

        if action.lower() == "remove empty":
            before = len(df)
            mask_non_empty = clean_missing_text(df[col]).notna()
            df = df.loc[mask_non_empty].copy()
            removed = before - len(df)
            rows_removed += removed
            action_log.append(f"{col}: Remove empty -> removed {removed} rows")
            columns_touched += 1
            continue

        if action.lower().startswith("replace with "):
            before_nulls = int(clean_missing_text(df[col]).isna().sum())
            df[col] = apply_replace_action(df[col], action)
            after_nulls = int(pd.Series(df[col]).isna().sum())
            action_log.append(
                f"{col}: {action} -> nulls {before_nulls} -> {after_nulls}"
            )
            columns_touched += 1

    final_rows = len(df)
    final_cols = len(df.columns)
    total_cells_null_after = int(df.isna().sum().sum())

    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("Listing null replacement summary\n")
        f.write(f"Input file: {merged_file}\n")
        f.write(f"Actions file: {actions_file}\n")
        f.write(f"Output file: {out_file}\n")
        f.write(f"Initial rows: {initial_rows}\n")
        f.write(f"Initial columns: {initial_cols}\n")
        f.write(f"Rows removed by 'Remove empty': {rows_removed}\n")
        f.write(f"Columns touched by actions: {columns_touched}\n")
        f.write(f"Final rows: {final_rows}\n")
        f.write(f"Final columns: {final_cols}\n")
        f.write(f"Total null cells before: {total_cells_null_before}\n")
        f.write(f"Total null cells after: {total_cells_null_after}\n")
        f.write("\nAction log:\n")
        for line in action_log:
            f.write(f"- {line}\n")

    print("Null replacement completed.")
    print(f"Initial rows: {initial_rows}")
    print(f"Final rows: {final_rows}")
    print(f"Rows removed by 'Remove empty': {rows_removed}")
    print(f"Columns touched by actions: {columns_touched}")
    print(f"Total null cells before: {total_cells_null_before}")
    print(f"Total null cells after: {total_cells_null_after}")
    print(f"Saved output: {out_file}")
    print(f"Saved summary: {summary_file}")


if __name__ == "__main__":
    main()
