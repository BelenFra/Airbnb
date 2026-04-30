#!/usr/bin/env python3
"""
Train and compare Random Forest vs HistGradientBoosting for nightly log(price).

Loads: modeling/property_pricing_modeling_dataset.csv (read-only).

Writes NEW artifacts under:
  modeling/training_outputs_property_pricing/

Model selection: highest validation R^2 (tie-break: lower validation RMSE).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "modeling" / "property_pricing_modeling_dataset.csv"
OUT_DIR = ROOT / "modeling" / "training_outputs_property_pricing"
RANDOM_STATE = 42

DROP_FROM_X = ("listing_id", "host_id", "price")
TARGET = "log_price"

CATEGORICAL_FEATURES = [
    "City",
    "room_type",
    "property_type",
    "neighbourhood_cleansed",
    "neighbourhood_group_cleansed",
    "bathrooms_text",
]


def build_strata(df: pd.DataFrame) -> pd.Series:
    raw = df["City"].astype(str) + "|" + df["room_type"].astype(str)
    counts = raw.value_counts()
    return raw.where(raw.isin(counts.index[counts >= 25]), "__rare_city_room_combo")


def make_preprocessor(num_cols: list[str], cat_cols: list[str]) -> ColumnTransformer:

    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )

    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, num_cols),
            ("cat", categorical_pipe, cat_cols),
        ],
        verbose_feature_names_out=True,
    )


def metrics_triplet(y_true, y_pred) -> dict[str, float]:
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }


def aggregate_transformer_importances(
    transformer_feature_names: np.ndarray,
    raw_importances: np.ndarray,
    categorical_columns: list[str],
) -> pd.DataFrame:
    buckets: dict[str, float] = {}

    cats_desc = sorted(categorical_columns, key=len, reverse=True)

    for name, score in zip(transformer_feature_names, raw_importances):
        imp = float(score)
        if name.startswith("num__"):
            base = name[5:]
        elif name.startswith("cat__"):
            # ColumnTransformer + OHE can emit `cat___col_value` (extra `_`); strip it.
            rest = name[4:].lstrip("_")
            base = None
            for col in cats_desc:
                prefix = col + "_"
                if rest.startswith(prefix):
                    base = col
                    break
            if base is None:
                base = rest
        else:
            base = name

        buckets[base] = buckets.get(base, 0.0) + imp

    out = pd.DataFrame({"feature": list(buckets.keys()), "importance": list(buckets.values())})
    return out.sort_values("importance", ascending=False).reset_index(drop=True)



def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    y = df[TARGET]

    strata = build_strata(df)

    if strata.value_counts().min() < 2:
        bad = strata.value_counts()[strata.value_counts() < 2]
        raise RuntimeError(f"Cannot stratify tiny buckets: {bad}")

    X = df.drop(columns=[TARGET, *DROP_FROM_X])

    numeric_features = [c for c in X.columns if c not in CATEGORICAL_FEATURES]

    base_preprocessor = make_preprocessor(numeric_features, CATEGORICAL_FEATURES)

    X_tv, X_test, y_tv, y_test, strata_tv, _ = train_test_split(
        X,
        y,
        strata,
        test_size=0.20,
        stratify=strata,
        random_state=RANDOM_STATE,
    )

    X_train, X_val, y_train, y_val = train_test_split(
        X_tv,
        y_tv,
        test_size=0.25,
        stratify=strata_tv,
        random_state=RANDOM_STATE,
    )

    specifications: dict[str, object] = {
        "RF_shallow_sqrt_features": RandomForestRegressor(
            n_estimators=240,
            max_depth=22,
            min_samples_leaf=6,
            max_features="sqrt",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "RF_deeper_frac_features": RandomForestRegressor(
            n_estimators=340,
            max_depth=None,
            min_samples_leaf=2,
            min_samples_split=4,
            max_features=0.45,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "HistGBDT_moderate_depth": HistGradientBoostingRegressor(
            learning_rate=0.06,
            max_depth=8,
            max_iter=300,
            l2_regularization=0.08,
            min_samples_leaf=30,
            early_stopping=True,
            validation_fraction=0.12,
            random_state=RANDOM_STATE,
        ),
        "HistGBDT_deeper_faster_lr": HistGradientBoostingRegressor(
            learning_rate=0.10,
            max_depth=11,
            max_iter=460,
            l2_regularization=0.02,
            min_samples_leaf=16,
            early_stopping=True,
            validation_fraction=0.10,
            random_state=RANDOM_STATE,
        ),
    }

    records: list[dict[str, object]] = []
    fitted: dict[str, Pipeline] = {}

    for tag, estimator in specifications.items():
        pipe = Pipeline(
            steps=[
                ("prep", clone(base_preprocessor)),
                ("model", estimator),
            ]
        )

        pipe.fit(X_train, y_train)

        tr = metrics_triplet(y_train, pipe.predict(X_train))
        va = metrics_triplet(y_val, pipe.predict(X_val))
        te = metrics_triplet(y_test, pipe.predict(X_test))

        records.append(
            {
                "model": tag,
                "train_r2": tr["r2"],
                "val_r2": va["r2"],
                "val_rmse": va["rmse"],
                "test_r2": te["r2"],
                "test_rmse": te["rmse"],
                "test_mae": te["mae"],
            }
        )

        fitted[tag] = pipe

    comparison = pd.DataFrame(records)

    ranking = comparison.sort_values(["val_r2", "val_rmse"], ascending=[False, True]).reset_index(drop=True)

    ranking.to_csv(OUT_DIR / "model_comparison_table.csv", index=False)

    pd.DataFrame(
        {
            "dataset_split": ["train", "validation", "test"],
            "row_count": [len(X_train), len(X_val), len(X_test)],
        }
    ).to_csv(OUT_DIR / "data_split_sizes.csv", index=False)

    best_tag = ranking.loc[0, "model"]
    champ = fitted[best_tag]

    tf_names = champ.named_steps["prep"].get_feature_names_out()

    native = aggregate_transformer_importances(
        tf_names,
        champ.named_steps["model"].feature_importances_,
        CATEGORICAL_FEATURES,
    )

    native.to_csv(OUT_DIR / "feature_importance_native_aggregated.csv", index=False)

    permute = permutation_importance(
        champ,
        X_val,
        y_val,
        n_repeats=7,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    permutation_tbl = pd.DataFrame(
        {
            "feature": X.columns,
            "perm_importance_mean": permute.importances_mean,
            "perm_importance_std": permute.importances_std,
        }
    ).sort_values("perm_importance_mean", ascending=False)

    permutation_tbl.to_csv(OUT_DIR / "feature_importance_permutation_validation.csv", index=False)

    top_native = native.head(15)
    top_perm = permutation_tbl.head(15)

    memo_lines = [
        "PROPERTY / PRICING — MODEL COMPARISON (MEMORANDUM STYLE)",
        "",
        "Question: Explain nightly Airbnb price variation with hedonic structural + ",
        "host descriptors (identifiers and nightly price purposely withheld from predictors).",
        "",
        f"Target column: `{TARGET}` (tabular `price` excluded from inputs).",
        f"Artifacts directory: {(OUT_DIR.relative_to(ROOT)).as_posix()}",
        "",
        "### Sample design",
        f"- Rows: train={len(X_train):,}; validation={len(X_val):,}; held-out test={len(X_test):,} (~60 / 20 / 20).",
        "- Stratification: City|room_type with rare combos (<25 listings pooled) preserves metro mix ",
        "  while satisfying sklearn stratified splitter minimums.",
        "- Preprocessing: median imputation numerics (covers sparse host super-host NA); categorical ",
        "  constant fill `'missing'` + one-hot encoder for tree learners.",
        "",
        "### Model leaderboard (ordering by validation merit)",
        ranking.to_string(index=False, float_format=lambda v: f"{v:.6f}"),
        "",
        f"**Selected champion**: `{best_tag}`.",
        "**Rule**: prioritize validation `R²`, ties broken by lower validation RMSE.",
        "",
        "### Why investors should care about validation—not test scores",
        "Test metrics are withheld for sanity checks until final reporting; premature optimization on ",
        "test leakage would inflate client confidence artificially.",
        "",
        "### Interpretation artifacts",
        "- `feature_importance_native_aggregated.csv`: internal split-based importances summed across exploded categories.",
        "- `feature_importance_permutation_validation.csv`: permutation mean drops in validation accuracy when scrambling each column;",
        "  higher values imply stronger nonlinear contribution after controlling for preprocessing.",
        "",
        "#### Top aggregated native drivers",
    ]

    for idx, (_, row) in enumerate(top_native.iterrows(), start=1):
        memo_lines.append(f"{idx}. {row['feature']:<40} {row['importance']:.5f}")

    memo_lines.extend(
        [
            "",
            "#### Top permutation validation drivers (± stdev)",
        ]
    )

    for idx, (_, row) in enumerate(top_perm.iterrows(), start=1):
        memo_lines.append(
            f"{idx}. {row['feature']:<40} {row['perm_importance_mean']:.6f} ± "
            f"{row['perm_importance_std']:.6f}"
        )

    memo_lines.extend(
        [
            "",
            "### Investor takeaways (associative—not causal appraisals)",
            "",
            "| Theme | Operational lens |",
            "|-------|------------------|",
            "| Market archetype (`City`, `room_type`, `property_type`) | Mirrors hotel STR segmentation—entire-home inventory typically clears higher ADR than partial-home / shared stock. |",
            "| Geography (`longitude`, latitude, neighbourhood_* ) | Signals micro-market willingness-to-pay beyond headline city averages. |",
            "| Sleeping capacity (`accommodates`, `bedrooms`, `beds`, `bathroom` stack) | Bigger sleeper counts unlock group demand when regulation allows;",
            "| underwrite furnishing + housekeeping costs versus modeled uplift. |",
            "| Stay-policy levers (`minimum_*`/`maximum_*` nights) | High minimum-night rules filter corporate/leisure bursts—validate calendar velocity assumptions. |",
            "| Operational amenities (pool/HVAC/workspace/parking, etc.) | Binary amenities describe amenity surcharge potential relative to comps;",
            "| translate into capex timelines before underwriting ROI. |",
            "",
            "Statistical caveat: correlations reflect co-movements in scraped listings—they do not certify incremental rent from renovating alone.",
            "Use blended judgment with comps, zoning, and tax counsel.",
        ]
    )

    (OUT_DIR / "memo_interpretation_property_pricing.txt").write_text(
        "\n".join(memo_lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
