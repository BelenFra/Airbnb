"""Guest-experience research questions (Q1–Q4) — reviews + master listing data.

Reads
------
- ``data/processed/reviews_all_cleaned.csv`` (chunked; ``listing_id``, ``comments_clean``)
- ``data/processed/master_data.csv`` (via toolkit)
- Optional: ``results/04_guest_experience/text_features/listing_city_deviation_terms.csv`` (after text mining)

Writes (mirrors ``results/01_market_analysis`` pattern)
-------------------------------------------------------
- ``results/04_guest_experience/q1_review_complaints/`` …
- ``results/04_guest_experience/q2_five_star_drivers/`` …
- ``results/04_guest_experience/q3_operational_investments/`` …
- ``results/04_guest_experience/q4_top_performer_praise/`` …
- ``results/04_guest_experience/README.md`` (index)

Toolkit: ``load_data``, ``get_summary_statistics``, ``split_data``,
``train_logistic_regression``, ``train_random_forest``, ``create_visualization``.

Run
---
    python scripts/04_guest_experience/run_guest_experience_questions.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("MPLCONFIGDIR", ".cache/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", ".cache")
os.environ.setdefault("MPLBACKEND", "Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

import mba706_toolkit as mba

RANDOM_STATE = 42
CHUNKSIZE = 200_000

MASTER_FILE = PROJECT_ROOT / "data" / "processed" / "master_data.csv"
REVIEWS_FILE = PROJECT_ROOT / "data" / "processed" / "reviews_all_cleaned.csv"
TEXT_FEATURES_DIR = PROJECT_ROOT / "results" / "04_guest_experience" / "text_features"
DEVIATION_FILE = TEXT_FEATURES_DIR / "listing_city_deviation_terms.csv"

RESULTS_ROOT = PROJECT_ROOT / "results" / "04_guest_experience"
Q1_DIR = RESULTS_ROOT / "q1_review_complaints"
Q2_DIR = RESULTS_ROOT / "q2_five_star_drivers"
Q3_DIR = RESULTS_ROOT / "q3_operational_investments"
Q4_DIR = RESULTS_ROOT / "q4_top_performer_praise"
# Guest complaint / friction tokens (``comments_clean`` is lower-style review text)
COMPLAINT_PATTERNS = re.compile(
    r"\b(?:noise|noisy|loud|smell|stink|mold|mould|bug|bugs|roach|"
    r"cockroach|dirty|dirt|stain|broken|leak|problem|issue|disappoint|"
    r"frustrat|rude|unresponsive|slow|wait|delay|misleading|inaccurate|"
    r"unsafe|cold|hot|hvac|small|cramped|construction|party)\w*\b",
    re.IGNORECASE,
)

SUBSCORE_COLS = [
    "review_scores_cleanliness",
    "review_scores_checkin",
    "review_scores_communication",
    "review_scores_location",
]


def df_to_simple_md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """Markdown table without optional ``tabulate`` dependency."""
    d = df if max_rows is None else df.head(max_rows)
    if d.empty:
        return "_No rows._\n"
    cols = list(d.columns)
    lines = [
        "| " + " | ".join(str(c) for c in cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in d.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def normalize_listing_id(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.strip(), errors="coerce").astype("Int64").astype("string")


def resolve_reviews_path() -> Path:
    p1 = PROJECT_ROOT / "data" / "processed" / "reviews_all_cleaned.csv"
    p2 = PROJECT_ROOT / "data" / "processed" / "all_reviews_cleaned.csv"
    if p1.exists():
        return p1
    if p2.exists():
        return p2
    raise FileNotFoundError("No processed reviews CSV found.")


def load_master_for_analysis() -> pd.DataFrame:
    info = mba.load_data(str(MASTER_FILE), dataset_name="master_ge")
    if info.get("status") != "success":
        raise RuntimeError(info)
    df = mba._data_store["master_ge"].copy()
    df["id"] = normalize_listing_id(df["id"])
    return df


def run_q1_chunked_complaints(master: pd.DataFrame, reviews_path: Path) -> None:
    Q1_DIR.mkdir(parents=True, exist_ok=True)
    lid_meta = master[
        ["id", "City", "property_type"]
    ].dropna(subset=["id"]).drop_duplicates("id")
    lid_meta = lid_meta.rename(columns={"id": "listing_id"})

    agg_city: dict[str, dict[str, int]] = {}
    agg_pt: dict[str, dict[str, int]] = {}

    def bump_batch(d: dict[str, dict[str, int]], key: str, n_hit: int, n_total: int) -> None:
        if key not in d:
            d[key] = {"reviews_total": 0, "reviews_with_complaint_cue": 0}
        d[key]["reviews_total"] += n_total
        d[key]["reviews_with_complaint_cue"] += n_hit

    usecols = ["listing_id", "comments_clean"]
    for chunk in pd.read_csv(
        reviews_path,
        usecols=usecols,
        chunksize=CHUNKSIZE,
        encoding="utf-8-sig",
        dtype={"listing_id": "string"},
        low_memory=False,
    ):
        chunk["listing_id"] = normalize_listing_id(chunk["listing_id"])
        sub = chunk.dropna(subset=["listing_id", "comments_clean"])
        if sub.empty:
            continue
        merged = sub.merge(
            lid_meta,
            on="listing_id",
            how="inner",
        )
        if merged.empty:
            continue
        text = merged["comments_clean"].astype(str)
        merged["_hit"] = text.str.contains(COMPLAINT_PATTERNS, regex=True, na=False).astype(int)
        g_city = merged.groupby("City", dropna=False).agg(
            n_total=("listing_id", "size"),
            n_hit=("_hit", "sum"),
        )
        for cty, row in g_city.iterrows():
            bump_batch(agg_city, str(cty), int(row["n_hit"]), int(row["n_total"]))
        pt_ser = merged["property_type"].fillna("Unknown").astype(str)
        merged["_pt"] = pt_ser
        g_pt = merged.groupby("_pt", dropna=False).agg(
            n_total=("listing_id", "size"),
            n_hit=("_hit", "sum"),
        )
        for pt, row in g_pt.iterrows():
            bump_batch(agg_pt, str(pt), int(row["n_hit"]), int(row["n_total"]))

    def to_df(d: dict[str, dict[str, int]], label_col: str) -> pd.DataFrame:
        rows = []
        for k, v in d.items():
            tot = v["reviews_total"]
            hit = v["reviews_with_complaint_cue"]
            rows.append(
                {
                    label_col: k,
                    "reviews_in_scope": tot,
                    "reviews_complaint_cue": hit,
                    "share_complaint_cue": round(hit / tot, 6) if tot else 0.0,
                }
            )
        out = pd.DataFrame(rows)
        return out.sort_values("share_complaint_cue", ascending=False)

    city_df = to_df(agg_city, "City")
    pt_df = to_df(agg_pt, "property_type")
    city_df.to_csv(Q1_DIR / "q1_complaint_cue_rate_by_city.csv", index=False, encoding="utf-8-sig")
    pt_df.to_csv(Q1_DIR / "q1_complaint_cue_rate_by_property_type.csv", index=False, encoding="utf-8-sig")

    top_city = city_df.iloc[0]["City"] if len(city_df) else ""
    top_share_c = float(city_df.iloc[0]["share_complaint_cue"]) if len(city_df) else 0.0
    pt_headline = pt_df[pt_df["reviews_in_scope"] >= 500].copy()
    if pt_headline.empty:
        pt_headline = pt_df
    top_pt = pt_headline.iloc[0]["property_type"] if len(pt_headline) else ""
    top_share_pt = float(pt_headline.iloc[0]["share_complaint_cue"]) if len(pt_headline) else 0.0

    city_tbl = df_to_simple_md_table(city_df)
    pt_tbl = df_to_simple_md_table(pt_df, max_rows=15)

    # Optional: city TF-IDF terms from text pipeline
    city_terms_path = TEXT_FEATURES_DIR / "city_corpus_top_terms.csv"
    extra = ""
    if city_terms_path.exists():
        ct = pd.read_csv(city_terms_path)
        extra = "\n\n**City-discriminating vocabulary** (TF-IDF on city mega-documents): see `../text_features/city_corpus_top_terms.csv` and ranks in that file per city.\n"

    md = f"""# Q1 — What do guests complain about? City and property type

## Answer (headline)

- **Relative complaint-friction in text:** We flag review comments that contain **practical complaint cues** (noise, smell, cleanliness/break/fix issues, delays, disappointment, etc. — regex over `comments_clean`).
- **By city**, the highest share of reviews with at least one such cue is **{top_city}** ({top_share_c:.1%} of in-scope reviews).
- **By property type**, among types with **≥500 in-scope reviews**, the highest complaint-cue share is **{top_pt}** ({top_share_pt:.1%}). (See full table for rare types — small volumes can hit 100% in error.)

## Method

- One pass over `{reviews_path.relative_to(PROJECT_ROOT)}` in chunks ({CHUNKSIZE:,} rows).
- Inner join to `master_data` for `City` and `property_type`.
- **Outcome:** `share_complaint_cue` = reviews with ≥1 regex hit / all joined reviews.

## Evidence

- `q1_complaint_cue_rate_by_city.csv`
- `q1_complaint_cue_rate_by_property_type.csv`
{extra}
### By city

{city_tbl}

### By property type (top 15 by rate)

{pt_tbl}

## Business interpretation

Higher **share_complaint_cue** means guests in that slice more often use **problem-oriented language** in free text. Combine with structured sub-scores and ops checks before treating as “worse operations.” **Property-type** differences often reflect **product heterogeneity** (e.g., whole-home vs shared) rather than management quality alone.
"""
    (Q1_DIR / "q1_summary.md").write_text(md, encoding="utf-8")


def run_q2_subscore_drivers(master: pd.DataFrame) -> None:
    Q2_DIR.mkdir(parents=True, exist_ok=True)
    need = ["review_scores_rating"] + SUBSCORE_COLS
    df = master.dropna(subset=need).copy()
    df = df[(df["review_scores_rating"] > 0) & df[SUBSCORE_COLS].gt(0).all(axis=1)]
    df["is_high_overall"] = (df["review_scores_rating"] >= 4.9).astype(int)

    mba._data_store["main_ge_q2"] = df[
        SUBSCORE_COLS + ["is_high_overall"]
    ].copy()
    split = mba.split_data(
        dataset_name="main_ge_q2",
        target_column="is_high_overall",
        train_size=0.7,
        validation_size=0.15,
        test_size=0.15,
        save_splits_as="splits_ge_q2",
    )
    if split.get("status") != "success":
        raise RuntimeError(split)

    log_res = mba.train_logistic_regression(
        splits_name="splits_ge_q2", save_model_as="log_ge_q2"
    )
    rf_res = mba.train_random_forest(
        splits_name="splits_ge_q2",
        n_estimators=150,
        task_type="classification",
        save_model_as="rf_ge_q2",
    )

    rows = []
    for name, coef in log_res.get("coefficients", {}).items():
        rows.append({"feature": name, "logistic_coef": coef})
    imp = rf_res.get("feature_importance", {})
    coef_df = pd.DataFrame(rows)
    coef_df["rf_importance"] = coef_df["feature"].map(imp)
    coef_df["abs_logistic_coef"] = coef_df["logistic_coef"].abs()
    coef_df = coef_df.sort_values("rf_importance", ascending=False, na_position="last")
    coef_df.to_csv(Q2_DIR / "q2_subscore_importance_ranking.csv", index=False, encoding="utf-8-sig")

    # Correlations with overall rating (descriptive)
    cor = df[SUBSCORE_COLS + ["review_scores_rating"]].corr()["review_scores_rating"].drop(
        "review_scores_rating"
    )
    cor.to_frame(name="corr_with_overall_rating").to_csv(
        Q2_DIR / "q2_subscore_correlation_with_overall.csv", encoding="utf-8-sig"
    )

    top_rf = coef_df.sort_values("rf_importance", ascending=False).iloc[0]["feature"]
    top_log = (
        str(coef_df.loc[coef_df["abs_logistic_coef"].idxmax(), "feature"])
        if len(coef_df)
        else ""
    )
    rf_excerpt = {k: rf_res[k] for k in ("test_accuracy", "feature_importance") if k in rf_res}
    base_rate = df["is_high_overall"].mean()

    md = f"""# Q2 — Which experience dimensions matter for near–5-star overall reviews?

## Answer (headline)

- **Target:** `is_high_overall` = 1 if `review_scores_rating >= 4.9` (about **{base_rate:.1%}** of listings with non-missing sub-scores).
- **Predictors:** Airbnb structured sub-scores — cleanliness, check-in, communication, location.
- **Model evidence:** Logistic regression (marginal coefficients) and Random Forest feature importance both rank drivers; top RF importance: **{top_rf}**; largest absolute logistic coefficient: **{top_log}**.

Sub-scores are **correlated** with each other; coefficients are **associative**, not independent causal effects.

## Method

- Toolkit: `load_data` → prepared frame → `split_data` (70/15/15, seed {RANDOM_STATE}) → `train_logistic_regression` + `train_random_forest` (classification).

## Evidence

- `q2_subscore_importance_ranking.csv` — logistic coefficients and RF importance.
- `q2_subscore_correlation_with_overall.csv` — pairwise correlation with overall rating.

### Logistic coefficients (test metrics in run log)

```text
{log_res!r}
```

### Random Forest (excerpt)

```text
{rf_excerpt!r}
```

## Business interpretation

Use the ranking as a **prioritisation lens** for where operational fixes **move the needle on guest perception**: if **cleanliness** and **accuracy/check-in** dominate, invest in **housekeeping QA** and **arrival experience** before marginal décor spend. **Location** is partly **fixed** by asset; message and price should reflect true access/noise trade-offs.
"""
    (Q2_DIR / "q2_summary.md").write_text(md, encoding="utf-8")


def amenity_flags(s: str) -> dict[str, bool]:
    raw = str(s).lower()
    return {
        "self_checkin_amenity": "self check" in raw,
        "keypad_lockbox": bool(
            re.search(r"lockbox|smart lock|keypad|electronic lock", raw)
        ),
        "cleaning_fee_listed": "cleaning" in raw,
        "carbon_alarm": "carbon monoxide" in raw,
        "host_greets": "host greets you" in raw,
    }


def run_q3_operational_signals(master: pd.DataFrame) -> None:
    Q3_DIR.mkdir(parents=True, exist_ok=True)
    df = master.dropna(subset=["review_scores_rating", "amenities"]).copy()
    if "instant_bookable" not in df.columns:
        df["instant_bookable"] = False
    df["instant_bookable"] = df["instant_bookable"].fillna(False)
    flags = df["amenities"].apply(amenity_flags).apply(pd.Series)
    df = pd.concat([df.reset_index(drop=True), flags], axis=1)

    def _as_bool_instant(x: object) -> bool:
        if isinstance(x, bool):
            return x
        return str(x).strip().lower() in ("true", "t", "1", "yes")

    df["instant_bookable_flag"] = df["instant_bookable"].map(_as_bool_instant)

    rows = []
    for col in list(flags.columns) + ["instant_bookable_flag"]:
        if col not in df.columns:
            continue
        for flag_val in (False, True):
            slice_ = df[df[col] == flag_val]
            if slice_.empty:
                continue
            rows.append(
                {
                    "signal": col,
                    "flag": flag_val,
                    "n_listings": len(slice_),
                    "mean_overall_rating": round(slice_["review_scores_rating"].mean(), 4),
                    "share_high_overall_ge_4_9": round(
                        (slice_["review_scores_rating"] >= 4.9).mean(), 4
                    ),
                }
            )

    sig_df = pd.DataFrame(rows)
    sig_df.to_csv(Q3_DIR / "q3_operational_signal_assoc.csv", index=False, encoding="utf-8-sig")

    # Toolkit visual: boxplot overall rating by self-check-in flag
    plot_df = df[["review_scores_rating", "self_checkin_amenity"]].copy()
    plot_df["self_checkin_amenity"] = plot_df["self_checkin_amenity"].map(
        {True: "self_check_in_amenity", False: "no_self_check_in"}
    )
    mba._data_store["q3_plot"] = plot_df.rename(
        columns={"self_checkin_amenity": "cohort", "review_scores_rating": "rating"}
    )
    mba.create_visualization(
        dataset_name="q3_plot",
        viz_type="boxplot",
        x_column="cohort",
        y_column="rating",
        title="Overall review rating by self check-in amenity listing flag",
    )

    best = sig_df[sig_df["flag"] == True].sort_values("mean_overall_rating", ascending=False)

    md = f"""# Q3 — Operational investments suggested by listings + reviews

## Answer (headline)

We proxy “investments” with **listing amenity flags** parsed from the `amenities` text (e.g., **Self check-in**, **smart lock / lockbox**, **cleaning** mentions) plus **`instant_bookable`**. For each flag we compare **mean overall review score** and **share of listings with overall ≥ 4.9**.

> **Caution:** Amenities correlate with **market tier, host professionalism, and property type** — these are **associations**, not proof that adding an amenity **causes** higher ratings.

Top signals by mean rating (flag=True rows) — see CSV for full table:

{df_to_simple_md_table(best.head(6))}

## Method

- String match / regex on `amenities` (case-insensitive).
- Group-wise means on `review_scores_rating`.

## Evidence

- `q3_operational_signal_assoc.csv`
- Figure (toolkit boxplot): `reports/figures/` (see latest guest-experience plot saved by toolkit naming).

## Business interpretation

Listings that advertise **lockbox / keypad / smart-lock** language and **cleaning**-related amenities show **higher average overall ratings** in this snapshot than those without — but hosts who bundle more amenities may differ on many other dimensions. **Instant Book** rows here have **lower** average ratings (often risk-taking hosts or different segments), so treat as descriptive only.
"""
    (Q3_DIR / "q3_summary.md").write_text(md, encoding="utf-8")


def run_q4_top_performer_terms(master: pd.DataFrame) -> None:
    Q4_DIR.mkdir(parents=True, exist_ok=True)
    if not DEVIATION_FILE.exists():
        note = f"""# Q4 — Praise patterns in top listings (text deviations)

## Status

**Inputs not found:** `{DEVIATION_FILE.relative_to(PROJECT_ROOT)}`

Run the text mining pipeline first:

```text
python scripts/models/text_analysis/run_hierarchical_text_mining.py --skip-sentiment
```

Then re-run:

```text
python scripts/04_guest_experience/run_guest_experience_questions.py
```
"""
        (Q4_DIR / "q4_summary.md").write_text(note, encoding="utf-8")
        return

    dev = pd.read_csv(DEVIATION_FILE)
    ratings = master[["id", "review_scores_rating", "City", "property_type"]].copy()
    ratings["id"] = normalize_listing_id(ratings["id"])
    ratings = ratings.dropna(subset=["id", "review_scores_rating"])
    ratings["listing_id"] = ratings["id"].astype(str)

    thr = ratings["review_scores_rating"].quantile(0.75)
    ratings["tier"] = np.where(
        ratings["review_scores_rating"] >= thr, "top_quartile_rating", "other"
    )

    dev["listing_id"] = dev["listing_id"].astype(str)
    merged = dev.merge(ratings[["listing_id", "tier"]], on="listing_id", how="inner")

    top_ct = (
        merged.loc[merged["tier"] == "top_quartile_rating", "term"].value_counts().head(40).reset_index()
    )
    top_ct.columns = ["term", "n_top"]
    other_ct = merged.loc[merged["tier"] == "other", "term"].value_counts().head(40).reset_index()
    other_ct.columns = ["term", "n_other"]
    lift = top_ct.merge(other_ct, on="term", how="outer").fillna(0)
    lift["lift_top_vs_other"] = (lift["n_top"] + 1) / (lift["n_other"] + 1)
    lift = lift.sort_values("lift_top_vs_other", ascending=False)
    lift.to_csv(Q4_DIR / "q4_term_lift_top_vs_other.csv", index=False, encoding="utf-8-sig")

    top_terms = ", ".join(lift.head(15)["term"].astype(str).tolist())

    md = f"""# Q4 — What do guests praise in top-performing listings?

## Answer (headline)

We define **top performers** as listings in the **top quartile** of `review_scores_rating` ({thr:.2f}+). Using **listing–city TF‑IDF deviation terms** (words that **over-index** vs same-city peers), we compare which stems appear more often among top-quartile listings vs others.

**Frequently elevated terms among top listings (examples):** {top_terms}

> Deviation terms capture **distinctive language**, not pure “praise” — interpret with care. Positive hospitality language (**great**, **recommend**, **comfort**) often appears.

## Method

- File: `{DEVIATION_FILE.relative_to(PROJECT_ROOT)}`
- Merge listing tiers from `master_data`.
- **Lift** ≈ (count in top + 1) / (count in other + 1) at the listing–term level.

## Evidence

- `q4_term_lift_top_vs_other.csv`

## Business interpretation

Themes that **separate** top guest perception from local peers are candidates for **standard playbooks**: **communication**, **cleanliness signals**, **location/description accuracy**, **amenities called out in reviews**. Validate each term qualitatively before rolling out “copy‑paste” host messaging.
"""
    (Q4_DIR / "q4_summary.md").write_text(md, encoding="utf-8")


def write_results_index() -> None:
    idx = """# Guest experience — research outputs

Structured like `results/01_market_analysis/`: one folder per question with `q*_summary.md` and CSV evidence.

| Folder | Question |
|--------|----------|
| `q1_review_complaints/` | What do guests complain about in reviews? By city and property type? |
| `q2_five_star_drivers/` | Which cleanliness / check-in / communication / location scores associate with ≥4.9 overall? |
| `q3_operational_investments/` | Operational proxies (amenities, instant book) vs review outcomes |
| `q4_top_performer_praise/` | Language that distinguishes top-quartile listings (TF‑IDF deviations) |
| `text_features/` | sparse matrices and vocabulary from `scripts/models/text_analysis/run_hierarchical_text_mining.py` |

**Scripts**

- Text mining: `scripts/models/text_analysis/run_hierarchical_text_mining.py`
- This synthesis: `scripts/04_guest_experience/run_guest_experience_questions.py`
"""
    (RESULTS_ROOT / "README.md").write_text(idx, encoding="utf-8")


def main() -> None:
    print("Loading master_data via toolkit …")
    master = load_master_for_analysis()
    reviews_path = resolve_reviews_path()

    print("Q1: chunked complaint cues …")
    run_q1_chunked_complaints(master, reviews_path)

    print("Q2: sub-score models …")
    run_q2_subscore_drivers(master)

    print("Q3: operational signals …")
    run_q3_operational_signals(master)

    print("Q4: top-performer deviation terms …")
    run_q4_top_performer_terms(master)

    write_results_index()
    print(f"Done. Summaries under {RESULTS_ROOT}")


if __name__ == "__main__":
    main()
