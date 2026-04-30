"""
MBA 706 Analytics Toolkit — Function Reference for Cursor
===================================================================
Prof. Seyed Emadi | UNC Kenan-Flagler Business School

PURPOSE:
    This file defines ALL approved analytics functions for MBA 706.
    When writing Python code for data analysis, you MUST use these functions
    rather than writing raw scikit-learn, pandas, or matplotlib code directly.

INSTRUCTIONS FOR CURSOR:
    1. ONLY use the functions defined in this file for analytics tasks.
    2. Do NOT write raw scikit-learn model training code — use the wrappers below.
    3. Do NOT create your own train/test splits — use split_data().
    4. Do NOT build custom plots from scratch — use create_visualization() or the
       plotting built into each function. If a plot type is not available, use
       execute_python_code() with RANDOM_STATE=42.
    5. ALL randomized operations must use RANDOM_STATE = 42.
    6. Follow this standard workflow:
         a. load_data()           → Load the dataset
         b. get_column_info()     → Understand the columns
         c. get_summary_statistics() → Descriptive stats
         d. clean_data()          → Handle missing values, duplicates
         e. create_visualization()→ Explore distributions and relationships
         f. split_data()          → Split BEFORE any modeling
         g. train_*()             → Train one or more models
         h. evaluate_classifier_performance() → Detailed eval with ROC curves
         i. compare_models()      → Head-to-head comparison table
    7. Save all plots to the 'reports/figures/' directory.
    8. After every analysis, provide a BUSINESS INTERPRETATION, not just numbers.

REPRODUCIBILITY:
    All functions use RANDOM_STATE=42 internally. Every student running the same
    code on the same data will get identical results.

DATA ARCHITECTURE:
    - _data_store: dict that holds all loaded datasets and splits by name.
    - _model_store: dict that holds all trained models by name.
    Both are module-level globals shared across all functions.

DEPENDENCIES (install first):
    pip install pandas numpy matplotlib seaborn scikit-learn xgboost textblob wordcloud scipy

================================================================================
"""

import pandas as pd
import numpy as np
import json
import io
import os
import sys
import subprocess
import requests
from pathlib import Path

# Project root derived from toolkit location (works regardless of CWD).
_TOOLKIT_ROOT = Path(__file__).resolve().parent

# Ensure writable local cache defaults for script-based execution.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("MPLCONFIGDIR", str(_TOOLKIT_ROOT / ".cache" / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(_TOOLKIT_ROOT / ".cache"))
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, plot_tree
from sklearn.ensemble import (
    RandomForestClassifier,
    RandomForestRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
)
from sklearn.decomposition import PCA
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.metrics import (
    accuracy_score,
    r2_score,
    roc_auc_score,
    roc_curve,
    confusion_matrix,
    classification_report,
    silhouette_score,
    mean_squared_error,
    mean_absolute_error,
    precision_score,
    recall_score,
    f1_score,
)
# Lazy-load xgboost inside train_xgboost() only, because some environments
# can hard-fail at import time due to OpenMP runtime configuration.
xgb = None
_xgboost_native_safe = None
_xgboost_native_failure_reason = ""
from textblob import TextBlob
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from wordcloud import WordCloud
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.cluster.vq import kmeans2

warnings.filterwarnings("ignore")
os.makedirs(str(_TOOLKIT_ROOT / "reports" / "figures"), exist_ok=True)
os.makedirs(os.environ.get("MPLCONFIGDIR", str(_TOOLKIT_ROOT / ".cache" / "matplotlib")), exist_ok=True)


def _finalize_plot(fig=None):
    """Show plots only when explicitly requested; otherwise close to avoid blocking in scripts.

    Set environment variable MBA706_SHOW_PLOTS=1 to display plots interactively.
    """
    fig = fig if fig is not None else plt.gcf()
    show_env = os.environ.get("MBA706_SHOW_PLOTS", "0").strip().lower()
    show_requested = show_env in {"1", "true", "yes", "y", "on"}
    non_interactive = {"agg", "pdf", "ps", "svg", "cairo", "template"}
    backend = str(matplotlib.get_backend()).lower()
    if show_requested and not any(b in backend for b in non_interactive):
        plt.show()
    else:
        plt.close(fig)

# ---------------------------------------------------------------------------
# GLOBAL STATE
# ---------------------------------------------------------------------------
_data_store = {}   # Stores datasets by name. Key="main" is default.
_model_store = {}  # Stores trained models by name.
RANDOM_STATE = 42  # Single source of truth — NEVER change this.


# ===========================================================================
#  1. DATA LOADING
# ===========================================================================

def load_data(filepath, dataset_name="main"):
    """Load a CSV file into the data store.

    Args:
        filepath: Local path, URL, or Colab path to a CSV file.
        dataset_name: Key to store the DataFrame under (default: "main").

    Returns:
        dict with status, shape, column names, dtypes, missing values, and preview.

    Example:
        load_data("data/customers.csv")
        load_data("https://raw.githubusercontent.com/.../titanic.csv", dataset_name="titanic")
    """
    try:
        if filepath.startswith("http://") or filepath.startswith("https://"):
            df = pd.read_csv(io.StringIO(requests.get(filepath).text))
        else:
            df = pd.read_csv(filepath, encoding="utf-8-sig")
        _data_store[dataset_name] = df
        return {
            "status": "success",
            "source": filepath,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": df.isnull().sum().to_dict(),
            "preview": df.head(3).to_dict(orient="records"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def load_excel_data(filepath, sheet_name=0, dataset_name="main"):
    """Load an Excel sheet into the data store.

    Args:
        filepath: Local path to an .xlsx/.xls file.
        sheet_name: Sheet index or name (default: 0).
        dataset_name: Key to store DataFrame under.
    """
    try:
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        _data_store[dataset_name] = df
        return {
            "status": "success",
            "source": filepath,
            "sheet_name": sheet_name,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": df.isnull().sum().to_dict(),
            "preview": df.head(3).to_dict(orient="records"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def save_dataset_to_excel(dataset_name="main", output_path="analysis_output.xlsx", sheet_name="results"):
    """Save a dataset from _data_store to an Excel file."""
    try:
        df = _data_store[dataset_name]
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        return {
            "status": "success",
            "dataset_name": dataset_name,
            "output_path": output_path,
            "sheet_name": sheet_name,
            "shape": list(df.shape),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  2. DATA EXPLORATION
# ===========================================================================

def get_summary_statistics(dataset_name="main", columns=None):
    """Descriptive statistics (mean, std, min, max, quartiles) for numeric columns.

    Args:
        dataset_name: Which dataset to summarize.
        columns: List of specific column names, or None for all numeric.

    Returns:
        dict with statistics and missing value counts.

    Example:
        get_summary_statistics()
        get_summary_statistics(columns=["age", "income", "score"])
    """
    try:
        df = _data_store[dataset_name]
        df = df[columns] if columns else df.select_dtypes(include=[np.number])
        return {
            "status": "success",
            "statistics": df.describe().to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_column_info(dataset_name="main", column_name=None):
    """Get metadata about columns: dtype, unique count, missing count, top values.

    Args:
        dataset_name: Which dataset.
        column_name: Specific column, or None for overview of all columns.

    Returns:
        dict with column details.

    Example:
        get_column_info()                        # All columns overview
        get_column_info(column_name="gender")     # Single column detail
    """
    try:
        df = _data_store[dataset_name]
        if column_name:
            col = df[column_name]
            return {
                "status": "success",
                "column": column_name,
                "dtype": str(col.dtype),
                "unique": int(col.nunique()),
                "missing": int(col.isnull().sum()),
                "top_values": (
                    col.value_counts().head(10).to_dict()
                    if col.nunique() < 100
                    else "Too many unique values"
                ),
            }
        return {
            "status": "success",
            "columns": [
                {
                    "name": c,
                    "type": str(df[c].dtype),
                    "unique": int(df[c].nunique()),
                    "missing": int(df[c].isnull().sum()),
                }
                for c in df.columns
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  3. DATA CLEANING
# ===========================================================================

def clean_data(
    dataset_name="main",
    drop_duplicates=False,
    handle_missing="none",
    columns_to_drop=None,
    save_as="main",
):
    """Clean a dataset: duplicates, missing values, drop columns.

    Args:
        dataset_name: Source dataset name.
        drop_duplicates: If True, remove duplicate rows.
        handle_missing: One of "none", "drop_rows", "fill_mean", "fill_median".
        columns_to_drop: List of column names to remove.
        save_as: Name to store the cleaned dataset (default overwrites "main").

    Returns:
        dict with changes made and new shape.

    Example:
        clean_data(drop_duplicates=True, handle_missing="fill_mean",
                    columns_to_drop=["id", "timestamp"])
    """
    try:
        df = _data_store[dataset_name].copy()
        changes = []
        if columns_to_drop:
            df = df.drop(columns=columns_to_drop, errors="ignore")
            changes.append(f"Dropped columns: {columns_to_drop}")
        if drop_duplicates:
            before = len(df)
            df = df.drop_duplicates()
            changes.append(f"Removed {before - len(df)} duplicates")
        if handle_missing == "drop_rows":
            before = len(df)
            df = df.dropna()
            changes.append(f"Dropped {before - len(df)} rows with missing values")
        elif handle_missing == "fill_mean":
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].mean())
            changes.append("Filled numeric missing values with mean")
        elif handle_missing == "fill_median":
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
            changes.append("Filled numeric missing values with median")
        _data_store[save_as] = df
        return {"status": "success", "changes_made": changes, "new_shape": list(df.shape)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def merge_datasets(
    left_dataset_name,
    right_dataset_name,
    how="inner",
    on=None,
    left_on=None,
    right_on=None,
    suffixes=("_x", "_y"),
    save_as="merged",
):
    """Merge two datasets from the data store using pandas-style join behavior.

    Args:
        left_dataset_name: Name of the left dataset in _data_store.
        right_dataset_name: Name of the right dataset in _data_store.
        how: One of "left", "right", "inner", "outer".
        on: Shared join key column(s) in both datasets.
        left_on: Join key(s) from left dataset when names differ.
        right_on: Join key(s) from right dataset when names differ.
        suffixes: Suffixes for overlapping non-key columns.
        save_as: Name to store merged dataset.

    Returns:
        dict with merge status, shape, join details, and preview.

    Example:
        merge_datasets("customers", "orders", how="left", on="customer_id")
        merge_datasets("a", "b", how="inner", left_on="id_a", right_on="id_b")
    """
    try:
        if how not in {"left", "right", "inner", "outer"}:
            return {"status": "error", "message": "how must be one of: left, right, inner, outer"}

        left_df = _data_store[left_dataset_name]
        right_df = _data_store[right_dataset_name]

        merged = pd.merge(
            left_df,
            right_df,
            how=how,
            on=on,
            left_on=left_on,
            right_on=right_on,
            suffixes=suffixes,
        )
        _data_store[save_as] = merged
        return {
            "status": "success",
            "left_dataset": left_dataset_name,
            "right_dataset": right_dataset_name,
            "how": how,
            "rows": len(merged),
            "columns": list(merged.columns),
            "shape": list(merged.shape),
            "saved_as": save_as,
            "preview": merged.head(3).to_dict(orient="records"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def merge_left(
    left_dataset_name,
    right_dataset_name,
    on=None,
    left_on=None,
    right_on=None,
    suffixes=("_x", "_y"),
    save_as="merged_left",
):
    """Convenience wrapper for a left join."""
    return merge_datasets(
        left_dataset_name=left_dataset_name,
        right_dataset_name=right_dataset_name,
        how="left",
        on=on,
        left_on=left_on,
        right_on=right_on,
        suffixes=suffixes,
        save_as=save_as,
    )


def merge_right(
    left_dataset_name,
    right_dataset_name,
    on=None,
    left_on=None,
    right_on=None,
    suffixes=("_x", "_y"),
    save_as="merged_right",
):
    """Convenience wrapper for a right join."""
    return merge_datasets(
        left_dataset_name=left_dataset_name,
        right_dataset_name=right_dataset_name,
        how="right",
        on=on,
        left_on=left_on,
        right_on=right_on,
        suffixes=suffixes,
        save_as=save_as,
    )


def merge_inner(
    left_dataset_name,
    right_dataset_name,
    on=None,
    left_on=None,
    right_on=None,
    suffixes=("_x", "_y"),
    save_as="merged_inner",
):
    """Convenience wrapper for an inner join."""
    return merge_datasets(
        left_dataset_name=left_dataset_name,
        right_dataset_name=right_dataset_name,
        how="inner",
        on=on,
        left_on=left_on,
        right_on=right_on,
        suffixes=suffixes,
        save_as=save_as,
    )


def merge_outer(
    left_dataset_name,
    right_dataset_name,
    on=None,
    left_on=None,
    right_on=None,
    suffixes=("_x", "_y"),
    save_as="merged_outer",
):
    """Convenience wrapper for an outer join."""
    return merge_datasets(
        left_dataset_name=left_dataset_name,
        right_dataset_name=right_dataset_name,
        how="outer",
        on=on,
        left_on=left_on,
        right_on=right_on,
        suffixes=suffixes,
        save_as=save_as,
    )


def rename_columns(dataset_name="main", rename_map=None, save_as="main"):
    """Rename columns using a dict mapping old_name -> new_name."""
    try:
        if not isinstance(rename_map, dict) or not rename_map:
            return {"status": "error", "message": "rename_map must be a non-empty dict"}
        df = _data_store[dataset_name].copy()
        before_cols = list(df.columns)
        df = df.rename(columns=rename_map)
        _data_store[save_as] = df
        return {
            "status": "success",
            "renamed_columns": rename_map,
            "columns_before": before_cols,
            "columns_after": list(df.columns),
            "shape": list(df.shape),
            "saved_as": save_as,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def convert_column_types(dataset_name="main", type_map=None, errors="coerce", save_as="main"):
    """Convert column dtypes using a dict mapping column -> dtype."""
    try:
        if not isinstance(type_map, dict) or not type_map:
            return {"status": "error", "message": "type_map must be a non-empty dict"}
        if errors not in {"coerce", "raise", "ignore"}:
            return {"status": "error", "message": "errors must be one of: coerce, raise, ignore"}

        df = _data_store[dataset_name].copy()
        conversions = {}
        for col, dtype_target in type_map.items():
            if col not in df.columns:
                conversions[col] = "column_not_found"
                continue
            try:
                if dtype_target in {"numeric", "number", "float", "int", "integer"}:
                    df[col] = pd.to_numeric(df[col], errors=errors)
                    if dtype_target in {"int", "integer"}:
                        df[col] = df[col].astype("Int64")
                elif dtype_target in {"datetime", "date"}:
                    df[col] = pd.to_datetime(df[col], errors=errors)
                elif dtype_target in {"string", "str", "text"}:
                    df[col] = df[col].astype("string")
                elif dtype_target in {"category", "categorical"}:
                    df[col] = df[col].astype("category")
                elif dtype_target in {"bool", "boolean"}:
                    df[col] = df[col].astype("boolean")
                else:
                    df[col] = df[col].astype(dtype_target)
                conversions[col] = f"converted_to_{dtype_target}"
            except Exception as col_err:
                conversions[col] = f"error: {col_err}"
                if errors == "raise":
                    raise

        _data_store[save_as] = df
        return {
            "status": "success",
            "conversions": conversions,
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "shape": list(df.shape),
            "saved_as": save_as,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def handle_outliers_iqr(
    dataset_name="main",
    columns=None,
    action="cap",
    iqr_multiplier=1.5,
    save_as="main",
):
    """Handle numeric outliers with IQR rules by capping or row removal.

    Args:
        dataset_name: Source dataset in _data_store.
        columns: Numeric columns to process, or None for all numeric columns.
        action: "cap" (winsorize to bounds) or "remove_rows" (drop rows with outliers).
        iqr_multiplier: IQR multiplier for lower/upper fences (default 1.5).
        save_as: Output dataset name in _data_store.
    """
    try:
        if action not in {"cap", "remove_rows"}:
            return {"status": "error", "message": "action must be one of: cap, remove_rows"}

        df = _data_store[dataset_name].copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        target_cols = columns if columns else numeric_cols
        target_cols = [c for c in target_cols if c in numeric_cols]
        if not target_cols:
            return {"status": "error", "message": "No valid numeric columns found for outlier handling"}

        summary = {}
        if action == "remove_rows":
            before_rows = len(df)
            mask_keep = pd.Series(True, index=df.index)
            for col in target_cols:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower = q1 - iqr_multiplier * iqr
                upper = q3 + iqr_multiplier * iqr
                outlier_mask = (df[col] < lower) | (df[col] > upper)
                summary[col] = {"lower_bound": float(lower), "upper_bound": float(upper), "outliers": int(outlier_mask.sum())}
                mask_keep &= ~outlier_mask
            df = df.loc[mask_keep].copy()
            removed_rows = before_rows - len(df)
        else:
            removed_rows = 0
            for col in target_cols:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower = q1 - iqr_multiplier * iqr
                upper = q3 + iqr_multiplier * iqr
                outlier_mask = (df[col] < lower) | (df[col] > upper)
                summary[col] = {"lower_bound": float(lower), "upper_bound": float(upper), "outliers": int(outlier_mask.sum())}
                df[col] = df[col].clip(lower=lower, upper=upper)

        _data_store[save_as] = df
        return {
            "status": "success",
            "action": action,
            "columns_processed": target_cols,
            "iqr_multiplier": iqr_multiplier,
            "removed_rows": int(removed_rows),
            "outlier_summary": summary,
            "new_shape": list(df.shape),
            "saved_as": save_as,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  4. VISUALIZATION
# ===========================================================================

def create_visualization(
    dataset_name="main",
    viz_type="histogram",
    x_column=None,
    y_column=None,
    hue_column=None,
    title=None,
    save_plot=True,
):
    """Create common plot types. Saves to reports/figures/ directory.

    Args:
        dataset_name: Which dataset.
        viz_type: One of "histogram", "scatter", "correlation_heatmap", "bar", "boxplot".
        x_column: Column for x-axis (required for most types).
        y_column: Column for y-axis (scatter, boxplot).
        hue_column: Column for color-coding (scatter only).
        title: Custom plot title.
        save_plot: Whether to save to reports/figures/ directory.

    Returns:
        dict with status and saved file path.

    Example:
        create_visualization(viz_type="histogram", x_column="age")
        create_visualization(viz_type="scatter", x_column="age", y_column="income")
        create_visualization(viz_type="correlation_heatmap")
        create_visualization(viz_type="bar", x_column="department")
        create_visualization(viz_type="boxplot", x_column="region", y_column="salary")
    """
    try:
        df = _data_store[dataset_name]
        fig, ax = plt.subplots(figsize=(10, 6))
        if viz_type == "histogram":
            df[x_column].dropna().hist(bins=30, edgecolor="black", ax=ax)
            ax.set_xlabel(x_column)
            ax.set_ylabel("Frequency")
        elif viz_type == "scatter":
            scatter_kw = {}
            if hue_column and hue_column in df.columns:
                scatter_kw["c"] = df[hue_column]
                scatter_kw["cmap"] = "viridis"
            ax.scatter(df[x_column], df[y_column], alpha=0.6, **scatter_kw)
            ax.set_xlabel(x_column)
            ax.set_ylabel(y_column)
        elif viz_type == "correlation_heatmap":
            numeric_df = df.select_dtypes(include=[np.number])
            sns.heatmap(numeric_df.corr(), annot=True, cmap="coolwarm", fmt=".2f", ax=ax)
        elif viz_type == "bar":
            df[x_column].value_counts().head(10).plot(kind="bar", ax=ax, edgecolor="black")
            ax.set_ylabel("Count")
        elif viz_type == "boxplot":
            if y_column:
                df.boxplot(column=y_column, by=x_column, ax=ax)
            else:
                df[[x_column]].boxplot(ax=ax)
        ax.set_title(title or f"{viz_type.replace('_', ' ').title()}: {x_column or ''}")
        plt.tight_layout()
        plot_name = str(_TOOLKIT_ROOT / "reports" / "figures" / f"{viz_type}_{x_column or 'all'}.png")
        if save_plot:
            fig.savefig(plot_name, dpi=150, bbox_inches="tight")
        _finalize_plot(fig)
        return {"status": "success", "plot_saved": plot_name if save_plot else "not saved"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def calculate_correlation(dataset_name="main", col1=None, col2=None):
    """Calculate pairwise or full correlation matrix.

    Args:
        dataset_name: Which dataset.
        col1, col2: Two column names for pairwise. Omit both for full matrix.

    Returns:
        dict with correlation value or full matrix.

    Example:
        calculate_correlation(col1="age", col2="income")  # Single pair
        calculate_correlation()                             # Full matrix
    """
    try:
        df = _data_store[dataset_name]
        if col1 and col2:
            return {"status": "success", "correlation": round(df[col1].corr(df[col2]), 4)}
        corr = df.select_dtypes(include=[np.number]).corr()
        return {"status": "success", "correlation_matrix": corr.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def perform_pca(
    dataset_name="main",
    features=None,
    n_components=2,
    save_as="pca_output",
    save_plot=True,
):
    """Run PCA on numeric features and store component scores in _data_store.

    Args:
        dataset_name: Source dataset.
        features: Columns to include (default: all numeric).
        n_components: Number of principal components.
        save_as: Dataset name for PCA scores joined to original data.
        save_plot: Save 2D scatter plot if n_components >= 2.
    """
    try:
        df = _data_store[dataset_name].copy()
        X = df[features] if features else df.select_dtypes(include=[np.number])
        X = X.fillna(X.mean())
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        pca = PCA(n_components=n_components, random_state=RANDOM_STATE)
        comps = pca.fit_transform(X_scaled)
        comp_cols = [f"PC{i}" for i in range(1, n_components + 1)]
        pca_df = pd.DataFrame(comps, columns=comp_cols, index=df.index)
        output_df = pd.concat([df, pca_df], axis=1)
        _data_store[save_as] = output_df
        _model_store["pca_model"] = {
            "model": pca,
            "scaler": scaler,
            "features": list(X.columns),
            "type": "pca",
            "task": "dimensionality_reduction",
        }

        plot_path = None
        if n_components >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(pca_df["PC1"], pca_df["PC2"], alpha=0.6)
            ax.set_xlabel("PC1")
            ax.set_ylabel("PC2")
            ax.set_title("PCA: PC1 vs PC2")
            plt.tight_layout()
            plot_path = str(_TOOLKIT_ROOT / "reports" / "figures" / "pca_scatter.png")
            if save_plot:
                fig.savefig(plot_path, dpi=150, bbox_inches="tight")
            _finalize_plot(fig)

        return {
            "status": "success",
            "features_used": list(X.columns),
            "n_components": n_components,
            "explained_variance_ratio": np.round(pca.explained_variance_ratio_, 4).tolist(),
            "cumulative_explained_variance": float(np.round(pca.explained_variance_ratio_.sum(), 4)),
            "components": pd.DataFrame(
                pca.components_, columns=X.columns, index=comp_cols
            ).round(4).to_dict(),
            "saved_as": save_as,
            "plot_saved": plot_path if (save_plot and plot_path) else "not saved",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  5. CLUSTERING (Unsupervised Learning)
# ===========================================================================

def perform_elbow_analysis(dataset_name="main", features=None, max_k=10, save_plot=True):
    """Elbow plot + silhouette analysis for choosing optimal k in K-Means.

    RUN THIS BEFORE perform_kmeans_clustering if the optimal k is unknown.

    Args:
        dataset_name: Which dataset.
        features: List of column names to cluster on (default: all numeric).
        max_k: Maximum k to test (default: 10).

    Returns:
        dict with inertias, silhouette scores per k, and recommended k.

    Example:
        perform_elbow_analysis()
        perform_elbow_analysis(features=["age", "income", "spend"], max_k=8)
    """
    try:
        df = _data_store[dataset_name]
        X = df[features] if features else df.select_dtypes(include=[np.number])
        X = X.fillna(X.mean())
        X_scaled = StandardScaler().fit_transform(X)
        inertias = []
        sil_scores = []
        K_range = range(2, max_k + 1)
        for k in K_range:
            km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
            km.fit(X_scaled)
            inertias.append(km.inertia_)
            sil_scores.append(round(silhouette_score(X_scaled, km.labels_), 4))
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        ax1.plot(list(K_range), inertias, "bo-", linewidth=2)
        ax1.set_xlabel("Number of Clusters (k)")
        ax1.set_ylabel("Inertia (Within-Cluster Sum of Squares)")
        ax1.set_title("Elbow Plot")
        ax1.grid(True, alpha=0.3)
        ax2.plot(list(K_range), sil_scores, "ro-", linewidth=2)
        ax2.set_xlabel("Number of Clusters (k)")
        ax2.set_ylabel("Silhouette Score")
        ax2.set_title("Silhouette Analysis")
        ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_plot:
            fig.savefig(str(_TOOLKIT_ROOT / "reports" / "figures" / "elbow_analysis.png"), dpi=150, bbox_inches="tight")
        _finalize_plot(fig)
        best_k = list(K_range)[np.argmax(sil_scores)]
        return {
            "status": "success",
            "inertias": dict(zip([int(k) for k in K_range], [round(i, 2) for i in inertias])),
            "silhouette_scores": dict(zip([int(k) for k in K_range], sil_scores)),
            "recommended_k": best_k,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def perform_kmeans_clustering(dataset_name="main", n_clusters=3, features=None, save_model_as="kmeans"):
    """K-Means clustering with silhouette score and cluster profiles.

    Args:
        dataset_name: Which dataset.
        n_clusters: Number of clusters.
        features: Columns to use (default: all numeric).
        save_model_as: Name in _model_store.

    Returns:
        dict with cluster sizes, silhouette score, interpretation, and cluster profiles.

    Example:
        perform_kmeans_clustering(n_clusters=4, features=["age", "income", "spend"])
    """
    try:
        df = _data_store[dataset_name].copy()
        X = df[features] if features else df.select_dtypes(include=[np.number])
        X = X.fillna(X.mean())
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        np.random.seed(RANDOM_STATE)
        centroids, labels = kmeans2(X_scaled, n_clusters, minit="++", iter=50)
        df["cluster"] = labels
        sil = silhouette_score(X_scaled, labels)
        _model_store[save_model_as] = {
            "model": {"centroids": centroids, "method": "scipy_kmeans2"},
            "scaler": scaler,
        }
        _data_store[dataset_name] = df
        profile = df.groupby("cluster")[X.columns.tolist()].mean().round(3).to_dict()
        return {
            "status": "success",
            "n_clusters": n_clusters,
            "cluster_sizes": df["cluster"].value_counts().sort_index().to_dict(),
            "silhouette_score": round(sil, 4),
            "interpretation": (
                "Good separation" if sil > 0.5
                else "Moderate separation" if sil > 0.25
                else "Poor separation — try different k"
            ),
            "cluster_profiles": profile,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def perform_hierarchical_clustering(
    dataset_name="main", n_clusters=3, features=None, linkage_method="ward", save_plot=True,
):
    """Hierarchical (agglomerative) clustering with dendrogram.

    Args:
        dataset_name: Which dataset.
        n_clusters: Number of clusters.
        features: Columns to use (default: all numeric).
        linkage_method: "ward", "complete", "average", or "single".

    Returns:
        dict with cluster sizes.

    Example:
        perform_hierarchical_clustering(n_clusters=3, linkage_method="ward")
    """
    try:
        df = _data_store[dataset_name].copy()
        X = df[features] if features else df.select_dtypes(include=[np.number])
        X_scaled = StandardScaler().fit_transform(X.fillna(X.mean()))
        hierarchical = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage_method)
        df["cluster"] = hierarchical.fit_predict(X_scaled)
        fig, ax = plt.subplots(figsize=(12, 6))
        dendrogram(linkage(X_scaled, method=linkage_method), ax=ax)
        ax.set_title(f"Dendrogram ({linkage_method} linkage)")
        ax.set_xlabel("Sample Index")
        ax.set_ylabel("Distance")
        plt.tight_layout()
        if save_plot:
            fig.savefig(str(_TOOLKIT_ROOT / "reports" / "figures" / "dendrogram.png"), dpi=150, bbox_inches="tight")
        _finalize_plot(fig)
        _data_store[dataset_name] = df
        return {
            "status": "success",
            "cluster_sizes": df["cluster"].value_counts().sort_index().to_dict(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  6. DATA SPLITTING
# ===========================================================================

def split_data(
    dataset_name="main",
    target_column=None,
    train_size=0.7,
    validation_size=0.15,
    test_size=0.15,
    save_splits_as="splits",
):
    """Split data into train/validation/test sets. MUST be called before any model training.

    Args:
        dataset_name: Source dataset.
        target_column: Column to predict (REQUIRED).
        train_size: Fraction for training (default: 0.7).
        validation_size: Fraction for validation (default: 0.15).
            Set to 0 for a simple 2-way train/test split.
        test_size: Fraction for test (default: 0.15).
        save_splits_as: Key in _data_store for the splits dict.

    Returns:
        dict with sample counts and feature names.

    Example:
        split_data(target_column="readmit30")                         # 70/15/15
        split_data(target_column="survived", train_size=0.7,
                   validation_size=0, test_size=0.3)                   # 70/30
    """
    try:
        df = _data_store[dataset_name]
        X_all = df.drop(columns=[target_column])
        X = X_all.select_dtypes(include=[np.number])
        dropped_cols = sorted(set(X_all.columns) - set(X.columns))
        y = df[target_column]
        total = train_size + validation_size + test_size
        if total <= 0:
            return {"status": "error", "message": "train_size + validation_size + test_size must be > 0"}
        train_size /= total
        validation_size /= total
        test_size /= total
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=test_size, random_state=RANDOM_STATE
        )
        if validation_size > 0.01:
            val_frac = validation_size / (train_size + validation_size)
            X_train, X_val, y_train, y_val = train_test_split(
                X_temp, y_temp, test_size=val_frac, random_state=RANDOM_STATE
            )
        else:
            X_train, y_train = X_temp, y_temp
            X_val, y_val = pd.DataFrame(), pd.Series(dtype=y.dtype)
        _data_store[save_splits_as] = {
            "X_train": X_train, "X_val": X_val, "X_test": X_test,
            "y_train": y_train, "y_val": y_val, "y_test": y_test,
            "feature_names": list(X.columns), "target_column": target_column,
        }
        result = {
            "status": "success",
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "features_used": list(X.columns),
        }
        if dropped_cols:
            result["non_numeric_columns_excluded"] = dropped_cols
        if len(X_val) > 0:
            result["validation_samples"] = len(X_val)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  7. SUPERVISED LEARNING — REGRESSION
# ===========================================================================

def train_linear_regression(splits_name="splits", save_model_as="linear_reg"):
    """Linear regression with coefficients, R-squared, and RMSE on all splits.

    Args:
        splits_name: Key in _data_store holding the splits dict.
        save_model_as: Key in _model_store.

    Returns:
        dict with intercept, coefficients, and metrics on train/val/test.

    Example:
        split_data(target_column="price")
        train_linear_regression()
    """
    try:
        splits = _data_store[splits_name]
        model = LinearRegression().fit(splits["X_train"], splits["y_train"])
        train_pred = model.predict(splits["X_train"])
        result = {
            "status": "success",
            "intercept": round(float(model.intercept_), 4),
            "coefficients": dict(zip(splits["feature_names"], model.coef_.round(4).tolist())),
            "training_r2": round(r2_score(splits["y_train"], train_pred), 4),
            "training_rmse": round(np.sqrt(mean_squared_error(splits["y_train"], train_pred)), 4),
        }
        if len(splits["X_val"]) > 0:
            val_pred = model.predict(splits["X_val"])
            result["validation_r2"] = round(r2_score(splits["y_val"], val_pred), 4)
            result["validation_rmse"] = round(np.sqrt(mean_squared_error(splits["y_val"], val_pred)), 4)
        test_pred = model.predict(splits["X_test"])
        result["test_r2"] = round(r2_score(splits["y_test"], test_pred), 4)
        result["test_rmse"] = round(np.sqrt(mean_squared_error(splits["y_test"], test_pred)), 4)
        _model_store[save_model_as] = {"model": model, "type": "linear_regression", "task": "regression"}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  8. SUPERVISED LEARNING — CLASSIFICATION
# ===========================================================================

def train_logistic_regression(splits_name="splits", save_model_as="logistic_reg", max_iter=1000):
    """Logistic regression with coefficients, accuracy, AUC, confusion matrix.

    Reports on training, validation (if exists), and test sets.

    Args:
        splits_name: Key in _data_store holding splits.
        save_model_as: Key in _model_store.
        max_iter: Max solver iterations (default: 1000).

    Returns:
        dict with intercept, coefficients, accuracy, AUC, confusion matrices.

    Example:
        split_data(target_column="readmit30")
        train_logistic_regression()
    """
    try:
        splits = _data_store[splits_name]
        model = LogisticRegression(max_iter=max_iter, random_state=RANDOM_STATE).fit(
            splits["X_train"], splits["y_train"]
        )
        train_pred = model.predict(splits["X_train"])
        result = {
            "status": "success",
            "intercept": round(float(model.intercept_[0]), 4),
            "coefficients": dict(zip(splits["feature_names"], model.coef_[0].round(4).tolist())),
            "training_accuracy": round(accuracy_score(splits["y_train"], train_pred), 4),
        }
        if len(np.unique(splits["y_train"])) == 2:
            train_proba = model.predict_proba(splits["X_train"])[:, 1]
            result["training_auc"] = round(roc_auc_score(splits["y_train"], train_proba), 4)
            cm = confusion_matrix(splits["y_train"], train_pred)
            if cm.shape == (2, 2):
                result["training_confusion_matrix"] = {"tn": int(cm[0,0]), "fp": int(cm[0,1]), "fn": int(cm[1,0]), "tp": int(cm[1,1])}
            else:
                result["training_confusion_matrix"] = cm.tolist()
        if len(splits["X_val"]) > 0:
            val_pred = model.predict(splits["X_val"])
            result["validation_accuracy"] = round(accuracy_score(splits["y_val"], val_pred), 4)
            if len(np.unique(splits["y_val"])) == 2:
                val_proba = model.predict_proba(splits["X_val"])[:, 1]
                result["validation_auc"] = round(roc_auc_score(splits["y_val"], val_proba), 4)
                cm = confusion_matrix(splits["y_val"], val_pred)
                if cm.shape == (2, 2):
                    result["validation_confusion_matrix"] = {"tn": int(cm[0,0]), "fp": int(cm[0,1]), "fn": int(cm[1,0]), "tp": int(cm[1,1])}
                else:
                    result["validation_confusion_matrix"] = cm.tolist()
        test_pred = model.predict(splits["X_test"])
        result["test_accuracy"] = round(accuracy_score(splits["y_test"], test_pred), 4)
        if len(np.unique(splits["y_test"])) == 2:
            test_proba = model.predict_proba(splits["X_test"])[:, 1]
            result["test_auc"] = round(roc_auc_score(splits["y_test"], test_proba), 4)
        _model_store[save_model_as] = {"model": model, "type": "logistic_regression", "task": "classification"}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def train_knn_classifier(splits_name="splits", n_neighbors=5, save_model_as="knn"):
    """K-Nearest Neighbors classifier.

    Args:
        splits_name: Key in _data_store.
        n_neighbors: Number of neighbors (default: 5).
        save_model_as: Key in _model_store.

    Returns:
        dict with accuracy on train/val/test.

    Example:
        train_knn_classifier(n_neighbors=7)
    """
    try:
        splits = _data_store[splits_name]
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(splits["X_train"])
        model = KNeighborsClassifier(n_neighbors=n_neighbors).fit(X_train_scaled, splits["y_train"])
        result = {
            "status": "success",
            "n_neighbors": n_neighbors,
            "training_accuracy": round(accuracy_score(splits["y_train"], model.predict(X_train_scaled)), 4),
        }
        if len(splits["X_val"]) > 0:
            result["validation_accuracy"] = round(
                accuracy_score(splits["y_val"], model.predict(scaler.transform(splits["X_val"]))), 4
            )
        result["test_accuracy"] = round(
            accuracy_score(splits["y_test"], model.predict(scaler.transform(splits["X_test"]))), 4
        )
        _model_store[save_model_as] = {"model": model, "scaler": scaler, "type": "knn", "task": "classification"}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def train_decision_tree(
    splits_name="splits", max_depth=5, task_type="classification", save_model_as="decision_tree", save_plot=True,
):
    """Decision Tree with tree visualization (top 3 levels shown).

    Args:
        splits_name: Key in _data_store.
        max_depth: Max depth of tree (default: 5).
        task_type: "classification" or "regression".
        save_model_as: Key in _model_store.

    Returns:
        dict with metrics and feature importance.

    Example:
        train_decision_tree(max_depth=4, task_type="classification")
    """
    try:
        splits = _data_store[splits_name]
        if task_type == "classification":
            model = DecisionTreeClassifier(max_depth=max_depth, random_state=RANDOM_STATE).fit(
                splits["X_train"], splits["y_train"]
            )
            train_metric = accuracy_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "accuracy"
        else:
            model = DecisionTreeRegressor(max_depth=max_depth, random_state=RANDOM_STATE).fit(
                splits["X_train"], splits["y_train"]
            )
            train_metric = r2_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "r2"
        result = {
            "status": "success",
            "max_depth": max_depth,
            "task_type": task_type,
            f"training_{metric_name}": round(train_metric, 4),
            "feature_importance": dict(sorted(
                zip(splits["feature_names"], model.feature_importances_.round(4).tolist()),
                key=lambda x: x[1], reverse=True,
            )),
        }
        if len(splits["X_val"]) > 0:
            val_pred = model.predict(splits["X_val"])
            key = "validation_accuracy" if task_type == "classification" else "validation_r2"
            metric_fn = accuracy_score if task_type == "classification" else r2_score
            result[key] = round(metric_fn(splits["y_val"], val_pred), 4)
        test_pred = model.predict(splits["X_test"])
        key = "test_accuracy" if task_type == "classification" else "test_r2"
        metric_fn = accuracy_score if task_type == "classification" else r2_score
        result[key] = round(metric_fn(splits["y_test"], test_pred), 4)
        # Tree visualization
        fig, ax = plt.subplots(figsize=(20, 10))
        plot_tree(model, feature_names=splits["feature_names"], filled=True, rounded=True, ax=ax, fontsize=8, max_depth=3)
        ax.set_title(f"Decision Tree (max_depth={max_depth})")
        plt.tight_layout()
        if save_plot:
            fig.savefig(str(_TOOLKIT_ROOT / "reports" / "figures" / "decision_tree.png"), dpi=150, bbox_inches="tight")
        _finalize_plot(fig)
        _model_store[save_model_as] = {"model": model, "type": "decision_tree", "task": task_type}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def train_neural_network(
    splits_name="splits", hidden_layers=(100, 50), task_type="classification", save_model_as="nn",
):
    """Neural network (MLP) classifier or regressor.

    Args:
        splits_name: Key in _data_store.
        hidden_layers: Tuple or list of hidden layer sizes (default: (100, 50)).
        task_type: "classification" or "regression".
        save_model_as: Key in _model_store.

    Returns:
        dict with architecture and metrics on train/val/test.

    Example:
        train_neural_network(hidden_layers=[64, 32], task_type="classification")
    """
    try:
        splits = _data_store[splits_name]
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(splits["X_train"])
        hl = tuple(hidden_layers) if isinstance(hidden_layers, list) else hidden_layers
        if task_type == "classification":
            model = MLPClassifier(hidden_layer_sizes=hl, max_iter=500, random_state=RANDOM_STATE).fit(
                X_train_scaled, splits["y_train"]
            )
            train_metric = accuracy_score(splits["y_train"], model.predict(X_train_scaled))
            metric_name = "accuracy"
        else:
            model = MLPRegressor(hidden_layer_sizes=hl, max_iter=500, random_state=RANDOM_STATE).fit(
                X_train_scaled, splits["y_train"]
            )
            train_metric = r2_score(splits["y_train"], model.predict(X_train_scaled))
            metric_name = "r2"
        result = {
            "status": "success",
            "architecture": list(model.hidden_layer_sizes),
            f"training_{metric_name}": round(train_metric, 4),
        }
        if len(splits["X_val"]) > 0:
            X_val_scaled = scaler.transform(splits["X_val"])
            val_pred = model.predict(X_val_scaled)
            key = f"validation_{metric_name}"
            metric_fn = accuracy_score if task_type == "classification" else r2_score
            result[key] = round(metric_fn(splits["y_val"], val_pred), 4)
        X_test_scaled = scaler.transform(splits["X_test"])
        test_pred = model.predict(X_test_scaled)
        key = f"test_{metric_name}"
        metric_fn = accuracy_score if task_type == "classification" else r2_score
        result[key] = round(metric_fn(splits["y_test"], test_pred), 4)
        _model_store[save_model_as] = {"model": model, "scaler": scaler, "type": "neural_network", "task": task_type}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def train_random_forest(
    splits_name="splits", n_estimators=100, task_type="classification", save_model_as="rf",
):
    """Random Forest classifier or regressor with feature importance.

    Args:
        splits_name: Key in _data_store.
        n_estimators: Number of trees (default: 100).
        task_type: "classification" or "regression".
        save_model_as: Key in _model_store.

    Returns:
        dict with metrics and sorted feature importance.

    Example:
        train_random_forest(n_estimators=200, task_type="classification")
    """
    try:
        splits = _data_store[splits_name]
        if task_type == "classification":
            model = RandomForestClassifier(n_estimators=n_estimators, random_state=RANDOM_STATE).fit(
                splits["X_train"], splits["y_train"]
            )
            train_metric = accuracy_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "accuracy"
        else:
            model = RandomForestRegressor(n_estimators=n_estimators, random_state=RANDOM_STATE).fit(
                splits["X_train"], splits["y_train"]
            )
            train_metric = r2_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "r2"
        importance = dict(sorted(
            zip(splits["feature_names"], model.feature_importances_.round(4).tolist()),
            key=lambda x: x[1], reverse=True,
        ))
        result = {
            "status": "success",
            "n_estimators": n_estimators,
            f"training_{metric_name}": round(train_metric, 4),
            "feature_importance": importance,
        }
        if len(splits["X_val"]) > 0:
            val_pred = model.predict(splits["X_val"])
            key = f"validation_{metric_name}"
            metric_fn = accuracy_score if task_type == "classification" else r2_score
            result[key] = round(metric_fn(splits["y_val"], val_pred), 4)
        test_pred = model.predict(splits["X_test"])
        key = f"test_{metric_name}"
        metric_fn = accuracy_score if task_type == "classification" else r2_score
        result[key] = round(metric_fn(splits["y_test"], test_pred), 4)
        _model_store[save_model_as] = {"model": model, "type": "random_forest", "task": task_type}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def train_gradient_boosting(
    splits_name="splits", n_estimators=100, task_type="classification", save_model_as="gbm",
):
    """Gradient Boosting classifier or regressor with feature importance.

    Args:
        splits_name: Key in _data_store.
        n_estimators: Number of boosting stages (default: 100).
        task_type: "classification" or "regression".
        save_model_as: Key in _model_store.
    """
    try:
        splits = _data_store[splits_name]
        if task_type == "classification":
            model = GradientBoostingClassifier(
                n_estimators=n_estimators, random_state=RANDOM_STATE
            ).fit(splits["X_train"], splits["y_train"])
            train_metric = accuracy_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "accuracy"
        else:
            model = GradientBoostingRegressor(
                n_estimators=n_estimators, random_state=RANDOM_STATE
            ).fit(splits["X_train"], splits["y_train"])
            train_metric = r2_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "r2"

        importance = dict(sorted(
            zip(splits["feature_names"], model.feature_importances_.round(4).tolist()),
            key=lambda x: x[1], reverse=True,
        ))
        result = {
            "status": "success",
            "n_estimators": n_estimators,
            f"training_{metric_name}": round(train_metric, 4),
            "feature_importance": importance,
        }
        if len(splits["X_val"]) > 0:
            val_pred = model.predict(splits["X_val"])
            key = f"validation_{metric_name}"
            metric_fn = accuracy_score if task_type == "classification" else r2_score
            result[key] = round(metric_fn(splits["y_val"], val_pred), 4)
        test_pred = model.predict(splits["X_test"])
        key = f"test_{metric_name}"
        metric_fn = accuracy_score if task_type == "classification" else r2_score
        result[key] = round(metric_fn(splits["y_test"], test_pred), 4)
        _model_store[save_model_as] = {"model": model, "type": "gradient_boosting", "task": task_type}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _is_xgboost_runtime_issue(error_message):
    """Detect common xgboost runtime failures where fallback is appropriate."""
    msg = str(error_message).lower()
    indicators = [
        "omp: error #179",
        "can't open shm2",
        "function can't open shm2",
        "openmp",
        "libomp",
        "kmp_",
    ]
    return any(indicator in msg for indicator in indicators)


def _xgboost_fallback_enabled():
    """Allow opt-out for strict environments by setting MBA706_XGBOOST_FALLBACK=0."""
    value = str(os.environ.get("MBA706_XGBOOST_FALLBACK", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _probe_xgboost_native_runtime():
    """Probe native xgboost fit in an isolated subprocess to avoid hard process aborts."""
    global _xgboost_native_safe
    global _xgboost_native_failure_reason
    if _xgboost_native_safe is not None:
        return _xgboost_native_safe, _xgboost_native_failure_reason

    code = (
        "from sklearn.datasets import load_breast_cancer\n"
        "from xgboost import XGBClassifier\n"
        "X, y = load_breast_cancer(return_X_y=True)\n"
        "m = XGBClassifier("
        "n_estimators=8,random_state=42,eval_metric='logloss',"
        "n_jobs=1,nthread=1,tree_method='hist',verbosity=0"
        ")\n"
        "m.fit(X, y)\n"
        "print('ok')\n"
    )
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("KMP_USE_SHM", "0")
    probe = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )

    if probe.returncode == 0 and "ok" in (probe.stdout or ""):
        _xgboost_native_safe = True
        _xgboost_native_failure_reason = ""
        return _xgboost_native_safe, _xgboost_native_failure_reason

    _xgboost_native_safe = False
    _xgboost_native_failure_reason = (probe.stderr or probe.stdout or "").strip() or "Unknown runtime failure"
    return _xgboost_native_safe, _xgboost_native_failure_reason


def _train_xgboost_sklearn_fallback(
    splits, n_estimators, task_type, save_model_as, failure_reason,
):
    """Fallback backend when native xgboost is unavailable in current runtime."""
    if task_type == "classification":
        model = GradientBoostingClassifier(
            n_estimators=n_estimators, random_state=RANDOM_STATE
        ).fit(splits["X_train"], splits["y_train"])
        train_metric = accuracy_score(splits["y_train"], model.predict(splits["X_train"]))
        metric_name = "accuracy"
    else:
        model = GradientBoostingRegressor(
            n_estimators=n_estimators, random_state=RANDOM_STATE
        ).fit(splits["X_train"], splits["y_train"])
        train_metric = r2_score(splits["y_train"], model.predict(splits["X_train"]))
        metric_name = "r2"

    importance = dict(sorted(
        zip(splits["feature_names"], model.feature_importances_.round(4).tolist()),
        key=lambda x: x[1], reverse=True,
    ))

    result = {
        "status": "success",
        "backend": "sklearn_gradient_boosting_fallback",
        "xgboost_status": "fallback_used",
        "xgboost_failure_reason": str(failure_reason),
        "n_estimators": n_estimators,
        f"training_{metric_name}": round(train_metric, 4),
        "feature_importance": importance,
    }
    if len(splits["X_val"]) > 0:
        val_pred = model.predict(splits["X_val"])
        key = f"validation_{metric_name}"
        metric_fn = accuracy_score if task_type == "classification" else r2_score
        result[key] = round(metric_fn(splits["y_val"], val_pred), 4)
    test_pred = model.predict(splits["X_test"])
    key = f"test_{metric_name}"
    metric_fn = accuracy_score if task_type == "classification" else r2_score
    result[key] = round(metric_fn(splits["y_test"], test_pred), 4)

    _model_store[save_model_as] = {
        "model": model,
        "type": "xgboost_fallback",
        "task": task_type,
        "backend": "sklearn_gradient_boosting",
    }
    return result


def train_xgboost(
    splits_name="splits", n_estimators=100, task_type="classification", save_model_as="xgb_model",
):
    """XGBoost classifier or regressor with feature importance.

    Args:
        splits_name: Key in _data_store.
        n_estimators: Number of boosting rounds (default: 100).
        task_type: "classification" or "regression".
        save_model_as: Key in _model_store.

    Returns:
        dict with metrics and sorted feature importance.
        If xgboost fails with known runtime issues (for example OpenMP SHM),
        this function falls back to sklearn Gradient Boosting by default.

    Example:
        train_xgboost(n_estimators=150, task_type="classification")
    """
    try:
        splits = _data_store[splits_name]
        fallback_allowed = _xgboost_fallback_enabled()
        native_safe, native_failure_reason = _probe_xgboost_native_runtime()
        if not native_safe:
            if fallback_allowed:
                return _train_xgboost_sklearn_fallback(
                    splits=splits,
                    n_estimators=n_estimators,
                    task_type=task_type,
                    save_model_as=save_model_as,
                    failure_reason=f"xgboost runtime probe failed: {native_failure_reason}",
                )
            return {
                "status": "error",
                "message": (
                    "xgboost runtime is unsafe in this environment and fallback is disabled. "
                    "Set MBA706_XGBOOST_FALLBACK=1 to use resilient fallback. "
                    f"Details: {native_failure_reason}"
                ),
            }
        global xgb
        if xgb is None:
            try:
                import xgboost as _xgb
                xgb = _xgb
            except Exception as import_err:
                if fallback_allowed:
                    return _train_xgboost_sklearn_fallback(
                        splits=splits,
                        n_estimators=n_estimators,
                        task_type=task_type,
                        save_model_as=save_model_as,
                        failure_reason=f"xgboost import failed: {import_err}",
                    )
                return {
                    "status": "error",
                    "message": (
                        "xgboost is unavailable in this environment. "
                        "Set MBA706_XGBOOST_FALLBACK=1 for automatic fallback. "
                        f"Details: {import_err}"
                    ),
                }
        if task_type == "classification":
            model = xgb.XGBClassifier(
                n_estimators=n_estimators,
                random_state=RANDOM_STATE,
                eval_metric="logloss",
                n_jobs=1,
                nthread=1,
                tree_method="hist",
                verbosity=0,
            ).fit(splits["X_train"], splits["y_train"])
            train_metric = accuracy_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "accuracy"
        else:
            model = xgb.XGBRegressor(
                n_estimators=n_estimators,
                random_state=RANDOM_STATE,
                n_jobs=1,
                nthread=1,
                tree_method="hist",
                verbosity=0,
            ).fit(
                splits["X_train"], splits["y_train"]
            )
            train_metric = r2_score(splits["y_train"], model.predict(splits["X_train"]))
            metric_name = "r2"
        importance = dict(sorted(
            zip(splits["feature_names"], model.feature_importances_.round(4).tolist()),
            key=lambda x: x[1], reverse=True,
        ))
        result = {
            "status": "success",
            "backend": "xgboost",
            "xgboost_status": "native_ok",
            "xgboost_version": getattr(xgb, "__version__", "unknown"),
            "n_estimators": n_estimators,
            f"training_{metric_name}": round(train_metric, 4),
            "feature_importance": importance,
        }
        if len(splits["X_val"]) > 0:
            val_pred = model.predict(splits["X_val"])
            key = f"validation_{metric_name}"
            metric_fn = accuracy_score if task_type == "classification" else r2_score
            result[key] = round(metric_fn(splits["y_val"], val_pred), 4)
        test_pred = model.predict(splits["X_test"])
        key = f"test_{metric_name}"
        metric_fn = accuracy_score if task_type == "classification" else r2_score
        result[key] = round(metric_fn(splits["y_test"], test_pred), 4)
        _model_store[save_model_as] = {"model": model, "type": "xgboost", "task": task_type}
        return result
    except Exception as e:
        if _xgboost_fallback_enabled() and _is_xgboost_runtime_issue(e):
            try:
                splits = _data_store[splits_name]
                return _train_xgboost_sklearn_fallback(
                    splits=splits,
                    n_estimators=n_estimators,
                    task_type=task_type,
                    save_model_as=save_model_as,
                    failure_reason=f"xgboost fit failed: {e}",
                )
            except Exception as fallback_err:
                return {
                    "status": "error",
                    "message": (
                        "xgboost failed and fallback model also failed. "
                        f"xgboost_error={e} | fallback_error={fallback_err}"
                    ),
                }
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  9. MODEL EVALUATION & COMPARISON
# ===========================================================================

def evaluate_classifier_performance(model_name, splits_name="splits", save_plot=True):
    """Full classifier evaluation: confusion matrix + ROC curve on all splits.

    Produces side-by-side ROC curves for training, validation (if exists), and test.

    Args:
        model_name: Key in _model_store (must be a trained classification model).
        splits_name: Key in _data_store.

    Returns:
        dict with accuracy, AUC, confusion matrix per split.

    Example:
        train_logistic_regression()
        evaluate_classifier_performance("logistic_reg")
    """
    try:
        model_info = _model_store[model_name]
        splits = _data_store[splits_name]
        results = {}
        datasets = {"training": ("X_train", "y_train"), "test": ("X_test", "y_test")}
        if len(splits["X_val"]) > 0:
            datasets["validation"] = ("X_val", "y_val")
        fig, axes = plt.subplots(1, len(datasets), figsize=(7 * len(datasets), 6))
        if len(datasets) == 1:
            axes = [axes]
        for idx, (name, (X_key, y_key)) in enumerate(datasets.items()):
            X = splits[X_key]
            y = splits[y_key]
            if "scaler" in model_info:
                X = model_info["scaler"].transform(X)
            y_pred = model_info["model"].predict(X)
            cm = confusion_matrix(y, y_pred)
            set_result = {
                "accuracy": round(accuracy_score(y, y_pred), 4),
            }
            if cm.shape == (2, 2):
                set_result["confusion_matrix"] = {"tn": int(cm[0,0]), "fp": int(cm[0,1]), "fn": int(cm[1,0]), "tp": int(cm[1,1])}
            else:
                set_result["confusion_matrix"] = cm.tolist()
            if hasattr(model_info["model"], "predict_proba"):
                y_proba = model_info["model"].predict_proba(X)[:, 1]
                fpr, tpr, _ = roc_curve(y, y_proba)
                auc_val = roc_auc_score(y, y_proba)
                set_result["auc_roc"] = round(auc_val, 4)
                axes[idx].plot(fpr, tpr, linewidth=2, label=f"AUC = {auc_val:.4f}")
                axes[idx].plot([0, 1], [0, 1], "k--", alpha=0.5)
                axes[idx].set_xlabel("False Positive Rate")
                axes[idx].set_ylabel("True Positive Rate")
                axes[idx].set_title(f"ROC — {name.title()} ({model_name})")
                axes[idx].legend(loc="lower right")
                axes[idx].grid(True, alpha=0.3)
            results[name] = set_result
        plt.tight_layout()
        if save_plot:
            fig.savefig(str(_TOOLKIT_ROOT / "reports" / "figures" / f"roc_{model_name}.png"), dpi=150, bbox_inches="tight")
        _finalize_plot(fig)
        return {"status": "success", **results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def compare_models(model_names, splits_name="splits", save_plot=True):
    """Compare multiple trained models on test set. Produces comparison table and bar chart.

    For classification: accuracy, precision, recall, F1, AUC.
    For regression: R², RMSE, MAE.

    Args:
        model_names: List of model name strings (keys in _model_store).
        splits_name: Key in _data_store.

    Returns:
        dict with comparison table.

    Example:
        train_logistic_regression(save_model_as="logistic_reg")
        train_random_forest(save_model_as="rf")
        train_xgboost(save_model_as="xgb_model")
        compare_models(["logistic_reg", "rf", "xgb_model"])
    """
    try:
        splits = _data_store[splits_name]
        comparison = []
        for name in model_names:
            if name not in _model_store:
                comparison.append({"model": name, "error": "Model not found"})
                continue
            model_info = _model_store[name]
            X_test = splits["X_test"]
            y_test = splits["y_test"]
            if "scaler" in model_info:
                X_test = model_info["scaler"].transform(X_test)
            y_pred = model_info["model"].predict(X_test)
            row = {"model": name, "type": model_info["type"]}
            if model_info.get("task", "classification") == "classification":
                row["accuracy"] = round(accuracy_score(y_test, y_pred), 4)
                row["precision"] = round(precision_score(y_test, y_pred, average="weighted", zero_division=0), 4)
                row["recall"] = round(recall_score(y_test, y_pred, average="weighted", zero_division=0), 4)
                row["f1_score"] = round(f1_score(y_test, y_pred, average="weighted", zero_division=0), 4)
                if hasattr(model_info["model"], "predict_proba") and len(np.unique(y_test)) == 2:
                    y_proba = model_info["model"].predict_proba(X_test)[:, 1]
                    row["auc_roc"] = round(roc_auc_score(y_test, y_proba), 4)
            else:
                row["r2"] = round(r2_score(y_test, y_pred), 4)
                row["rmse"] = round(np.sqrt(mean_squared_error(y_test, y_pred)), 4)
                row["mae"] = round(mean_absolute_error(y_test, y_pred), 4)
            comparison.append(row)
        comp_df = pd.DataFrame(comparison)
        print("\nModel Comparison (Test Set):")
        print("=" * 80)
        print(comp_df.to_string(index=False))
        print("=" * 80)
        if save_plot and len(comparison) > 1:
            fig, ax = plt.subplots(figsize=(10, 5))
            metric_col = "accuracy" if "accuracy" in comp_df.columns else "r2"
            if metric_col in comp_df.columns:
                comp_df.plot(x="model", y=metric_col, kind="bar", ax=ax, legend=False, edgecolor="black")
                ax.set_title(f"Model Comparison — {metric_col.title()}")
                ax.set_ylabel(metric_col.title())
                ax.set_xlabel("")
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                fig.savefig(str(_TOOLKIT_ROOT / "reports" / "figures" / "model_comparison.png"), dpi=150, bbox_inches="tight")
                _finalize_plot(fig)
        return {"status": "success", "comparison": comparison}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
# 10. TEXT ANALYTICS
# ===========================================================================

def perform_sentiment_analysis(dataset_name="main", text_column=None):
    """Sentiment analysis using TextBlob. Adds sentiment and sentiment_cat columns.

    Args:
        dataset_name: Which dataset.
        text_column: Column containing text to analyze (REQUIRED).

    Returns:
        dict with sentiment distribution and average sentiment.

    Example:
        perform_sentiment_analysis(text_column="review_text")
    """
    try:
        if text_column is None:
            return {"status": "error", "message": "text_column is required"}
        df = _data_store[dataset_name].copy()
        df["sentiment"] = df[text_column].apply(
            lambda x: TextBlob(str(x)).sentiment.polarity if pd.notna(x) else 0
        )
        df["sentiment_cat"] = df["sentiment"].apply(
            lambda x: "positive" if x > 0.1 else "negative" if x < -0.1 else "neutral"
        )
        _data_store[dataset_name] = df
        fig, ax = plt.subplots(figsize=(10, 5))
        df["sentiment_cat"].value_counts().plot(kind="bar", ax=ax, edgecolor="black")
        ax.set_title("Sentiment Distribution")
        ax.set_ylabel("Count")
        plt.tight_layout()
        fig.savefig(str(_TOOLKIT_ROOT / "reports" / "figures" / "sentiment.png"), dpi=150, bbox_inches="tight")
        _finalize_plot(fig)
        return {
            "status": "success",
            "distribution": df["sentiment_cat"].value_counts().to_dict(),
            "avg_sentiment": round(df["sentiment"].mean(), 4),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_bag_of_words(dataset_name="main", text_column=None, max_features=100, save_as="bow_features"):
    """Create bag-of-words features from text with word cloud visualization.

    Args:
        dataset_name: Which dataset.
        text_column: Column containing text (REQUIRED).
        max_features: Vocabulary size limit (default: 100).
        save_as: Name for the augmented dataset.

    Returns:
        dict with vocabulary size and top 20 words.

    Example:
        create_bag_of_words(text_column="comments", max_features=50)
    """
    try:
        if text_column is None:
            return {"status": "error", "message": "text_column is required"}
        df = _data_store[dataset_name]
        vectorizer = CountVectorizer(max_features=max_features, stop_words="english")
        bow_matrix = vectorizer.fit_transform(df[text_column].fillna(""))
        bow_df = pd.DataFrame(bow_matrix.toarray(), columns=vectorizer.get_feature_names_out())
        _data_store[save_as] = pd.concat([df.reset_index(drop=True), bow_df], axis=1)
        wordcloud = WordCloud(width=800, height=400).generate_from_frequencies(bow_df.sum().to_dict())
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.axis("off")
        ax.set_title("Word Cloud")
        fig.savefig(str(_TOOLKIT_ROOT / "reports" / "figures" / "wordcloud.png"), dpi=150, bbox_inches="tight")
        _finalize_plot(fig)
        return {
            "status": "success",
            "vocabulary_size": len(vectorizer.get_feature_names_out()),
            "top_words": bow_df.sum().sort_values(ascending=False).head(20).to_dict(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_tfidf_features(
    dataset_name="main",
    text_column=None,
    max_features=500,
    ngram_range=(1, 2),
    save_as="tfidf_features",
):
    """Create TF-IDF features from text and store augmented dataset.

    Args:
        dataset_name: Source dataset key.
        text_column: Column containing text (REQUIRED).
        max_features: Vocabulary cap.
        ngram_range: Tuple like (1,1) or (1,2).
        save_as: Output dataset key.
    """
    try:
        if text_column is None:
            return {"status": "error", "message": "text_column is required"}
        df = _data_store[dataset_name]
        vectorizer = TfidfVectorizer(
            max_features=max_features, stop_words="english", ngram_range=ngram_range
        )
        tfidf = vectorizer.fit_transform(df[text_column].fillna("").astype(str))
        tfidf_df = pd.DataFrame(tfidf.toarray(), columns=vectorizer.get_feature_names_out())
        _data_store[save_as] = pd.concat([df.reset_index(drop=True), tfidf_df], axis=1)
        top_terms = tfidf_df.mean().sort_values(ascending=False).head(20).round(4).to_dict()
        return {
            "status": "success",
            "vocabulary_size": len(vectorizer.get_feature_names_out()),
            "top_terms_by_avg_tfidf": top_terms,
            "ngram_range": list(ngram_range),
            "saved_as": save_as,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def scrape_web_table(
    url,
    table_index=0,
    match=None,
    dataset_name="scraped_table",
    save_excel_path=None,
):
    """Scrape an HTML table from a web page and optionally save to Excel.

    Args:
        url: Web page URL containing one or more HTML tables.
        table_index: Which table to select (0-based) if match is not used.
        match: Optional regex/string to match a specific table header/content.
        dataset_name: Key to store scraped DataFrame.
        save_excel_path: Optional path to write scraped table to .xlsx.
    """
    try:
        if match:
            tables = pd.read_html(url, match=match)
        else:
            tables = pd.read_html(url)
        if not tables:
            return {"status": "error", "message": "No tables found at URL"}
        if table_index < 0 or table_index >= len(tables):
            return {"status": "error", "message": f"table_index must be between 0 and {len(tables)-1}"}
        df = tables[table_index]
        _data_store[dataset_name] = df
        result = {
            "status": "success",
            "url": url,
            "tables_found": len(tables),
            "selected_table_index": table_index,
            "rows": len(df),
            "columns": list(df.columns),
            "saved_as": dataset_name,
            "preview": df.head(3).to_dict(orient="records"),
        }
        if save_excel_path:
            with pd.ExcelWriter(save_excel_path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="scraped_table", index=False)
            result["excel_saved"] = save_excel_path
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def train_naive_bayes_text_classifier(
    dataset_name="main",
    text_column=None,
    target_column=None,
    max_features=5000,
    ngram_range=(1, 2),
    test_size=0.2,
    save_model_as="nb_text",
):
    """Train a Multinomial Naive Bayes text classifier using TF-IDF features.

    Args:
        dataset_name: Source dataset key.
        text_column: Text feature column (REQUIRED).
        target_column: Target class column (REQUIRED).
        max_features: Max TF-IDF vocabulary size.
        ngram_range: N-gram range for TF-IDF (e.g., (1,1), (1,2)).
        test_size: Fraction for test split.
        save_model_as: Key to store trained model in _model_store.
    """
    try:
        if text_column is None or target_column is None:
            return {"status": "error", "message": "text_column and target_column are required"}

        df = _data_store[dataset_name].copy()
        if text_column not in df.columns or target_column not in df.columns:
            return {"status": "error", "message": "text_column or target_column not found in dataset"}

        model_df = df[[text_column, target_column]].dropna().copy()
        X_text = model_df[text_column].astype(str)
        y = model_df[target_column]

        X_train_text, X_test_text, y_train, y_test = train_test_split(
            X_text, y, test_size=test_size, random_state=RANDOM_STATE
        )

        vectorizer = TfidfVectorizer(
            max_features=max_features, stop_words="english", ngram_range=ngram_range
        )
        X_train = vectorizer.fit_transform(X_train_text)
        X_test = vectorizer.transform(X_test_text)

        model = MultinomialNB()
        model.fit(X_train, y_train)

        y_train_pred = model.predict(X_train)
        y_test_pred = model.predict(X_test)

        result = {
            "status": "success",
            "algorithm": "MultinomialNB",
            "rows_used": int(len(model_df)),
            "class_distribution": y.value_counts().to_dict(),
            "vocabulary_size": int(len(vectorizer.get_feature_names_out())),
            "training_accuracy": round(accuracy_score(y_train, y_train_pred), 4),
            "test_accuracy": round(accuracy_score(y_test, y_test_pred), 4),
            "test_precision_weighted": round(precision_score(y_test, y_test_pred, average="weighted", zero_division=0), 4),
            "test_recall_weighted": round(recall_score(y_test, y_test_pred, average="weighted", zero_division=0), 4),
            "test_f1_weighted": round(f1_score(y_test, y_test_pred, average="weighted", zero_division=0), 4),
        }

        if len(np.unique(y_test)) == 2 and hasattr(model, "predict_proba"):
            y_proba = model.predict_proba(X_test)[:, 1]
            result["test_auc"] = round(roc_auc_score(y_test, y_proba), 4)

        cm = confusion_matrix(y_test, y_test_pred)
        result["test_confusion_matrix"] = cm.tolist()
        result["classification_report"] = classification_report(y_test, y_test_pred, output_dict=True, zero_division=0)

        feature_names = np.array(vectorizer.get_feature_names_out())
        class_names = [str(c) for c in model.classes_]
        top_terms = {}
        for i, cls in enumerate(class_names):
            top_idx = np.argsort(model.feature_log_prob_[i])[-15:][::-1]
            top_terms[cls] = feature_names[top_idx].tolist()
        result["top_terms_by_class"] = top_terms

        _model_store[save_model_as] = {
            "model": model,
            "vectorizer": vectorizer,
            "type": "naive_bayes_text",
            "task": "classification",
            "text_column": text_column,
            "target_column": target_column,
            "classes": class_names,
        }
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===========================================================================
# 11. CUSTOM CODE EXECUTION (escape hatch)
# ===========================================================================

def execute_python_code(code, description="Custom analytics"):
    """Execute arbitrary Python code for analyses NOT covered by other functions.

    USE THIS ONLY when no pre-built function exists (e.g., PCA, SVM, time series,
    ANOVA, custom dashboards). Always use RANDOM_STATE=42 for reproducibility.
    Save plots to 'reports/figures/' directory.

    Has access to: _data_store, _model_store, RANDOM_STATE, and all imported libraries.

    Args:
        code: Python code string to execute.
        description: Brief description of what the code does.

    Returns:
        dict with status and truncated code preview.

    Example:
        execute_python_code(
            code='''
from sklearn.decomposition import PCA
df = _data_store["main"]
X = df.select_dtypes(include=[np.number]).dropna()
pca = PCA(n_components=2, random_state=RANDOM_STATE)
components = pca.fit_transform(StandardScaler().fit_transform(X))
plt.figure(figsize=(10,8))
plt.scatter(components[:,0], components[:,1], alpha=0.5)
plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%})")
plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%})")
plt.title("PCA Biplot")
plt.savefig("reports/figures/pca.png", dpi=150, bbox_inches="tight")
plt.show()
            ''',
            description="PCA with 2 components"
        )
    """
    try:
        exec_globals = {
            "_data_store": _data_store,
            "_model_store": _model_store,
            "RANDOM_STATE": RANDOM_STATE,
            "pd": pd, "np": np, "plt": plt, "sns": sns, "json": json,
            "StandardScaler": StandardScaler, "train_test_split": train_test_split,
            "LinearRegression": LinearRegression, "LogisticRegression": LogisticRegression,
            "KMeans": KMeans,
            "RandomForestClassifier": RandomForestClassifier,
            "RandomForestRegressor": RandomForestRegressor,
            "DecisionTreeClassifier": DecisionTreeClassifier,
            "DecisionTreeRegressor": DecisionTreeRegressor,
            "xgb": xgb,
            "accuracy_score": accuracy_score, "r2_score": r2_score,
            "silhouette_score": silhouette_score,
            "confusion_matrix": confusion_matrix,
            "classification_report": classification_report,
            "roc_auc_score": roc_auc_score, "roc_curve": roc_curve,
            "__import__": __import__,
        }
        exec(code, exec_globals)
        return {
            "status": "success",
            "description": description,
            "code_executed": code[:200] + "..." if len(code) > 200 else code,
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "code": code[:300]}


# ===========================================================================
# QUICK REFERENCE — ALL AVAILABLE FUNCTIONS
# ===========================================================================
#
# DATA:
#   load_data(filepath, dataset_name="main")
#   get_summary_statistics(dataset_name="main", columns=None)
#   get_column_info(dataset_name="main", column_name=None)
#   clean_data(dataset_name, drop_duplicates, handle_missing, columns_to_drop, save_as)
#
# VISUALIZATION:
#   create_visualization(dataset_name, viz_type, x_column, y_column, hue_column, title)
#       viz_type: "histogram" | "scatter" | "correlation_heatmap" | "bar" | "boxplot"
#   calculate_correlation(dataset_name, col1, col2)
#
# CLUSTERING (Unsupervised):
#   perform_elbow_analysis(dataset_name, features, max_k)
#   perform_kmeans_clustering(dataset_name, n_clusters, features)
#   perform_hierarchical_clustering(dataset_name, n_clusters, features, linkage_method)
#
# DATA SPLITTING (always do this before modeling):
#   split_data(dataset_name, target_column, train_size, validation_size, test_size)
#
# SUPERVISED — REGRESSION:
#   train_linear_regression(splits_name)
#
# SUPERVISED — CLASSIFICATION:
#   train_logistic_regression(splits_name, max_iter)
#   train_knn_classifier(splits_name, n_neighbors)
#   train_decision_tree(splits_name, max_depth, task_type)
#   train_neural_network(splits_name, hidden_layers, task_type)
#   train_random_forest(splits_name, n_estimators, task_type)
#   train_xgboost(splits_name, n_estimators, task_type)
#
# EVALUATION:
#   evaluate_classifier_performance(model_name, splits_name)
#   compare_models(model_names, splits_name)
#
# TEXT:
#   perform_sentiment_analysis(dataset_name, text_column)
#   create_bag_of_words(dataset_name, text_column, max_features)
#
# ESCAPE HATCH:
#   execute_python_code(code, description)
#
# ===========================================================================
