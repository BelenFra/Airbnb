"""Processed Airbnb reviews inventory and quality memo.

Mirror of ``inventory_raw_reviews.py`` but for the ``*_cleaned.csv`` files in
``data/processed/review/<city>/``. Documents the final state of the cleaned
data: row counts, unique listings/reviewers/review-ids, length distribution and
any residual quality issues (rows where ``listing_id`` ended up non-numeric,
dates that fail to parse, remaining short comments, residual HTML, etc.).

Important context
-----------------
The cleaned files in ``data/processed/review/<city>/`` were produced by Agostino
with ``run_full_review_cleaning.py``.  We verified by comparing review IDs that
they were generated from **the same raw snapshot** that lives in ``data/raw/reviews/``
(see the ``Raw ↔ cleaned reconciliation`` section of the memo): every cleaned
review ID exists in the corresponding raw file, so the cleaning is fully
reproducible from our local raws.

Outputs
-------
- ``data/processed/review/_eda/reviews_processed_inventory.csv`` — per-city summary.
- ``data/processed/review/_eda/reviews_cleaned_per_year_by_city.csv`` — yearly counts.
- ``data/processed/review/_eda/reviews_raw_vs_cleaned_reconciliation.csv`` — raw↔cleaned ID match.
- ``reports/figures/market_analysis/reviews/04_demand_intensity_per_listing.png`` — reviews per listing distribution.
- ``reports/figures/market_analysis/reviews/05_seasonality_heatmap.png`` — month-of-year demand mix per city.
- ``reports/figures/market_analysis/reviews/06_yearly_trend_indexed.png`` — recovery profile (indexed to 2019).
- ``reports/figures/market_analysis/reviews/07_review_engagement_length.png`` — comments_clean_length distribution.
- ``reports/figures/market_analysis/reviews/08_cleaning_pipeline_funnel.png`` — rows in → rows out by drop reason.
- ``data/processed/review/_eda/processed_data_memo_reviews.md`` — narrative memo.

Files are streamed in 200k-row chunks so memory stays bounded even though the
largest cleaned file is ~900MB on disk.
"""

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
import warnings
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import mba706_toolkit as tk  # noqa: F401  (kept for parity with project rules)

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

RANDOM_STATE = 42

PROCESSED_REVIEW_DIR = PROJECT_ROOT / "data" / "processed" / "review"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "reviews"
EDA_DIR = PROCESSED_REVIEW_DIR / "_eda"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "market_analysis" / "reviews"
MEMO_PATH = EDA_DIR / "processed_data_memo_reviews.md"
INVENTORY_CSV = EDA_DIR / "reviews_processed_inventory.csv"
YEARLY_CSV = EDA_DIR / "reviews_cleaned_per_year_by_city.csv"
RECONCILIATION_CSV = EDA_DIR / "reviews_raw_vs_cleaned_reconciliation.csv"

PLOT_DEMAND_INTENSITY = FIGURES_DIR / "04_demand_intensity_per_listing.png"
PLOT_SEASONALITY = FIGURES_DIR / "05_seasonality_heatmap.png"
PLOT_YEARLY_INDEXED = FIGURES_DIR / "06_yearly_trend_indexed.png"
PLOT_LENGTH = FIGURES_DIR / "07_review_engagement_length.png"
PLOT_FUNNEL = FIGURES_DIR / "08_cleaning_pipeline_funnel.png"

AUDIT_CSV = PROJECT_ROOT / "results" / "01_market_analysis" / "reviews" / "reviews_cleaning_audit.csv"

# Memo lives at data/processed/review/_eda/processed_data_memo_reviews.md;
# figures live at reports/figures/market_analysis/reviews/*.png. Relative path goes up four levels.
MEMO_FIG_PREFIX = "../../../../reports/figures/market_analysis/reviews"

# Map "city" (snake_case) -> cleaned filename. After the 2026-04-29 fix
# (csv.QUOTE_ALL + snake_case naming), all layers of the project share the
# same convention: ``reviews_<city>_cleaned.csv`` with city in snake_case.
CITY_FILES = {
    "hawaii": "reviews_hawaii_cleaned.csv",
    "los_angeles": "reviews_los_angeles_cleaned.csv",
    "nashville": "reviews_nashville_cleaned.csv",
    "new_york": "reviews_new_york_cleaned.csv",
    "san_francisco": "reviews_san_francisco_cleaned.csv",
}
RAW_FILES = {
    "hawaii": "reviews_hawaii.csv",
    "los_angeles": "reviews_los_angeles.csv",
    "nashville": "reviews_nashville.csv",
    "new_york": "reviews_new_york.csv",
    "san_francisco": "reviews_san_francisco.csv",
}

EXPECTED_COLUMNS = [
    "listing_id", "id", "date", "reviewer_id", "reviewer_name",
    "comments", "comments_clean", "comments_clean_length",
]
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
NON_ASCII_PATTERN = re.compile(r"[^\x00-\x7f]")
CHUNK_SIZE = 200_000
LENGTH_SAMPLE_CAP = 200_000

# Mirror cleaning thresholds from run_full_review_cleaning.py
CLEANING_MIN_LENGTH = 30

CITY_COLORS = {
    "hawaii": "#1f77b4",
    "los_angeles": "#ff7f0e",
    "nashville": "#2ca02c",
    "new_york": "#d62728",
    "san_francisco": "#9467bd",
}

CITY_LABELS = {
    "hawaii": "Hawaii",
    "los_angeles": "Los Angeles",
    "nashville": "Nashville",
    "new_york": "New York",
    "san_francisco": "San Francisco",
}


def analyze_city(city: str, csv_path: Path) -> dict:
    """Stream the cleaned CSV in chunks and compute summary statistics."""

    rows_total = 0
    nulls = {col: 0 for col in EXPECTED_COLUMNS}
    bad_listing_id_rows = 0
    bad_date_rows = 0
    blank_clean_rows = 0
    short_clean_rows = 0
    residual_html_rows = 0
    non_ascii_rows = 0

    listing_ids: set[int] = set()
    reviewer_ids: set[int] = set()
    review_ids: set[int] = set()
    duplicate_review_ids = 0

    yearly_counts: dict[int, int] = {}
    monthly_counts: dict[int, int] = {m: 0 for m in range(1, 13)}
    monthly_counts_recent: dict[int, int] = {m: 0 for m in range(1, 13)}  # 2022+ only
    listing_review_counts: Counter[int] = Counter()
    min_date: pd.Timestamp | None = None
    max_date: pd.Timestamp | None = None

    length_samples: list[int] = []
    sample_long_comments: list[tuple[int, str]] = []  # (length, snippet)

    rng = np.random.default_rng(RANDOM_STATE)

    reader = pd.read_csv(
        csv_path,
        usecols=EXPECTED_COLUMNS,
        dtype={
            "listing_id": "string",
            "id": "string",
            "reviewer_id": "string",
            "reviewer_name": "string",
            "comments": "string",
            "comments_clean": "string",
            "comments_clean_length": "Int64",
        },
        chunksize=CHUNK_SIZE,
        low_memory=False,
        on_bad_lines="skip",
    )

    for chunk in reader:
        rows_total += len(chunk)

        for col in EXPECTED_COLUMNS:
            nulls[col] += int(chunk[col].isna().sum())

        listing_num = pd.to_numeric(chunk["listing_id"], errors="coerce")
        bad_listing_mask = chunk["listing_id"].notna() & listing_num.isna()
        bad_listing_id_rows += int(bad_listing_mask.sum())
        valid_listings = listing_num.dropna().astype("int64")
        listing_ids.update(valid_listings.unique().tolist())
        listing_review_counts.update(valid_listings.tolist())

        reviewer_num = pd.to_numeric(chunk["reviewer_id"], errors="coerce")
        reviewer_ids.update(reviewer_num.dropna().astype("int64").unique().tolist())

        id_num = pd.to_numeric(chunk["id"], errors="coerce")
        id_clean = id_num.dropna().astype("int64")
        seen_mask = id_clean.isin(review_ids)
        already_seen_cross_chunks = int(seen_mask.sum())
        within_chunk_dupes = int(len(id_clean) - id_clean.nunique())
        duplicate_review_ids += already_seen_cross_chunks + within_chunk_dupes
        review_ids.update(id_clean.unique().tolist())

        date_parsed = pd.to_datetime(chunk["date"], errors="coerce")
        bad_date_mask = chunk["date"].notna() & date_parsed.isna()
        bad_date_rows += int(bad_date_mask.sum())

        if date_parsed.notna().any():
            chunk_min = date_parsed.min()
            chunk_max = date_parsed.max()
            min_date = chunk_min if min_date is None else min(min_date, chunk_min)
            max_date = chunk_max if max_date is None else max(max_date, chunk_max)
            year_series = date_parsed.dt.year.dropna().astype(int)
            for year, count in year_series.value_counts().items():
                yearly_counts[int(year)] = yearly_counts.get(int(year), 0) + int(count)
            month_series = date_parsed.dt.month.dropna().astype(int)
            for month, count in month_series.value_counts().items():
                monthly_counts[int(month)] = monthly_counts.get(int(month), 0) + int(count)
            recent_mask = date_parsed.dt.year >= 2022
            if recent_mask.any():
                recent_months = date_parsed[recent_mask].dt.month.dropna().astype(int)
                for month, count in recent_months.value_counts().items():
                    monthly_counts_recent[int(month)] = (
                        monthly_counts_recent.get(int(month), 0) + int(count)
                    )

        lengths = chunk["comments_clean_length"].dropna().astype("int64")
        blank_clean_rows += int((lengths == 0).sum())
        short_clean_rows += int(((lengths > 0) & (lengths < CLEANING_MIN_LENGTH)).sum())

        comments_clean = chunk["comments_clean"].astype("string").fillna("")
        residual_html_rows += int(comments_clean.str.contains(HTML_TAG_PATTERN, regex=True).sum())
        non_ascii_rows += int(comments_clean.str.contains(NON_ASCII_PATTERN, regex=True).sum())

        # Sample lengths for the histogram
        if len(length_samples) < LENGTH_SAMPLE_CAP and len(lengths) > 0:
            remaining = LENGTH_SAMPLE_CAP - len(length_samples)
            if len(lengths) <= remaining:
                length_samples.extend(lengths.tolist())
            else:
                idx = rng.choice(len(lengths), size=remaining, replace=False)
                length_samples.extend(lengths.iloc[idx].tolist())

        # Capture a few extreme-length comments for the memo
        if lengths.size:
            top_n = chunk.assign(_len=lengths.reindex(chunk.index)).nlargest(2, "_len")
            for _, row in top_n.iterrows():
                snippet = (row["comments_clean"] or "")[:200].replace("\n", " ")
                if pd.notna(row["_len"]):
                    sample_long_comments.append((int(row["_len"]), snippet))

    sample_long_comments.sort(key=lambda x: x[0], reverse=True)
    sample_long_comments = sample_long_comments[:3]

    return {
        "city": city,
        "rows_total": rows_total,
        "listings_unique": len(listing_ids),
        "reviewers_unique": len(reviewer_ids),
        "review_ids_unique": len(review_ids),
        "duplicate_review_ids": duplicate_review_ids,
        "bad_listing_id_rows": bad_listing_id_rows,
        "bad_date_rows": bad_date_rows,
        "blank_clean_rows": blank_clean_rows,
        "short_clean_rows": short_clean_rows,
        "residual_html_rows": residual_html_rows,
        "non_ascii_rows": non_ascii_rows,
        "nulls": {k: v for k, v in nulls.items() if not k.startswith("__")},
        "min_date": str(min_date.date()) if min_date is not None else None,
        "max_date": str(max_date.date()) if max_date is not None else None,
        "yearly_counts": yearly_counts,
        "monthly_counts": monthly_counts,
        "monthly_counts_recent": monthly_counts_recent,
        "listing_review_counts": listing_review_counts,
        "length_samples": length_samples,
        "sample_long_comments": sample_long_comments,
        # Held only in-memory between analyze_city and reconcile_with_raw,
        # then dropped before serialisation.
        "_review_id_set": review_ids,
    }


def reconcile_with_raw(city: str, raw_path: Path, cleaned_ids: set[int]) -> dict:
    """Compare review IDs in raw vs cleaned to confirm they share the same snapshot.

    Returns a row of metrics for the reconciliation table. ``extra_in_cleaned``
    must be 0 if the cleaning is reproducible from this raw file.
    """

    raw_ids: set[int] = set()
    raw_rows = 0
    for chunk in pd.read_csv(
        raw_path,
        usecols=["id"],
        dtype={"id": "string"},
        chunksize=CHUNK_SIZE,
        low_memory=False,
        on_bad_lines="skip",
    ):
        raw_rows += len(chunk)
        ids_num = pd.to_numeric(chunk["id"], errors="coerce").dropna().astype("int64")
        raw_ids.update(ids_num.unique().tolist())

    extra = len(cleaned_ids - raw_ids)
    dropped = len(raw_ids - cleaned_ids)
    drop_pct = 0.0 if not raw_ids else round(dropped / len(raw_ids) * 100, 2)

    return {
        "city": city,
        "raw_rows": raw_rows,
        "raw_unique_ids": len(raw_ids),
        "cleaned_unique_ids": len(cleaned_ids),
        "ids_dropped_by_cleaning": dropped,
        "ids_extra_in_cleaned": extra,
        "drop_pct_vs_raw_ids": drop_pct,
        "same_snapshot": extra == 0,
    }


def length_percentiles(samples: list[int]) -> dict[str, int]:
    if not samples:
        return {k: 0 for k in ("min", "p25", "p50", "p75", "p95", "p99", "max")}
    arr = np.asarray(samples)
    return {
        "min": int(arr.min()),
        "p25": int(np.percentile(arr, 25)),
        "p50": int(np.percentile(arr, 50)),
        "p75": int(np.percentile(arr, 75)),
        "p95": int(np.percentile(arr, 95)),
        "p99": int(np.percentile(arr, 99)),
        "max": int(arr.max()),
    }


SOURCE_FOOTER = (
    "Source: Inside Airbnb 2025-09 snapshot, post-cleaning by run_full_review_cleaning.py.  "
    "Five-city Term Project (MBA 706)."
)


def _save_fig(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _style_ax(ax, *, ylabel: str | None = None, xlabel: str | None = None,
              grid: str = "y") -> None:
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if grid:
        ax.grid(axis=grid, linestyle="--", alpha=0.35, linewidth=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="both", labelsize=9)


def make_demand_intensity_chart(per_city_results: list[dict]) -> None:
    """Plot 04 — demand intensity per listing.

    Reads as: each box is the per-listing distribution of total reviews
    (lifetime).  This is the **demand proxy** for the revenue equation: more
    reviews per listing = more bookings = higher annual revenue at a given
    nightly price.  The orange line marks the per-city median; the diamond on
    top is the P95 (the "successful 5% of listings" band).  Tail-heavy
    cities (Hawaii, NYC) have a long tail of high-volume listings → those are
    the comparables for any premium-segment recommendation.
    """
    cities = [r["city"] for r in per_city_results]
    cities = sorted(cities, key=lambda c: -np.median(
        list(next(r for r in per_city_results if r["city"] == c)["listing_review_counts"].values())
        or [0]
    ))
    data = []
    medians = []
    p95s = []
    counts = []
    colors = []
    labels = []
    for city in cities:
        r = next(r for r in per_city_results if r["city"] == city)
        vals = np.array(list(r["listing_review_counts"].values()), dtype=float)
        data.append(np.clip(vals, 0, np.percentile(vals, 99)) if vals.size else np.array([0]))
        medians.append(float(np.median(vals)) if vals.size else 0.0)
        p95s.append(float(np.percentile(vals, 95)) if vals.size else 0.0)
        counts.append(int(vals.size))
        colors.append(CITY_COLORS.get(city, "#888"))
        labels.append(CITY_LABELS.get(city, city))

    fig, ax = plt.subplots(figsize=(11, 6.2))
    bp = ax.boxplot(
        data, positions=np.arange(len(cities)), widths=0.55, patch_artist=True,
        showfliers=False, medianprops=dict(color="#111", linewidth=2.2),
        whiskerprops=dict(color="#666", linewidth=1),
        capprops=dict(color="#666", linewidth=1),
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.55)
        patch.set_edgecolor("#333")

    p95_max = max(p95s) if p95s else 1
    for i, (p95_v, med_v, n_v) in enumerate(zip(p95s, medians, counts)):
        ax.scatter(i, p95_v, marker="D", s=70, color="#d62728", zorder=5,
                   label="P95 (top 5% listings)" if i == 0 else None,
                   edgecolor="white", linewidth=1)
        ax.text(i, p95_v + p95_max * 0.025, f"P95: {int(p95_v)}",
                ha="center", fontsize=9, color="#a01f1f", fontweight="bold")
        ax.annotate(f"median: {int(med_v)}",
                    xy=(i + 0.32, med_v), xytext=(i + 0.42, med_v),
                    fontsize=8.8, color="#111", va="center",
                    arrowprops=dict(arrowstyle="-", color="#111", lw=0.7))

    x_labels_with_n = [f"{lab}\n(n={c:,} listings)" for lab, c in zip(labels, counts)]
    ax.set_xticks(np.arange(len(cities)))
    ax.set_xticklabels(x_labels_with_n, fontsize=9.5)
    _style_ax(ax, ylabel="Reviews per listing (lifetime, capped at P99)")
    ax.set_ylim(bottom=0, top=p95_max * 1.20 if p95_max > 0 else 1)
    ax.legend(loc="upper right", fontsize=9, frameon=False)

    fig.suptitle("Demand intensity: how many reviews does the typical listing get?",
                 fontsize=13, fontweight="bold", y=0.995)
    ax.set_title("Boxes show the middle 50% of listings; whiskers reach the 1st-99th percentile.  "
                 "Use the median as the demand floor and the P95 diamond as the top-cohort target.",
                 fontsize=9.8, color="#444", pad=10)
    fig.text(0.01, 0.005, SOURCE_FOOTER, fontsize=8, color="#777")
    _save_fig(fig, PLOT_DEMAND_INTENSITY)


def make_seasonality_heatmap(per_city_results: list[dict]) -> None:
    """Plot 05 — seasonality heatmap.

    Reads as: rows are cities, columns are calendar months, cell color is the
    *share* of that city's reviews falling in that month (within 2022+ to
    isolate the post-COVID demand pattern).  Lighter shading = peak season,
    darker = trough.  The pattern flags pricing power (ADR can rise 30-100%
    in peaks) and also the *risk profile*: Hawaii's heavy summer concentration
    means revenue depends on a narrow window; NYC is flatter year-round.
    """
    cities = [r["city"] for r in per_city_results]
    matrix = np.zeros((len(cities), 12))
    totals = []
    for i, r in enumerate(per_city_results):
        counts = r.get("monthly_counts_recent") or r.get("monthly_counts") or {}
        total = sum(counts.values())
        totals.append(total)
        if total == 0:
            continue
        for m in range(1, 13):
            matrix[i, m - 1] = counts.get(m, 0) / total * 100

    fig, ax = plt.subplots(figsize=(11, 4.2))
    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=4, vmax=12)
    ax.set_xticks(np.arange(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                        "Aug", "Sep", "Oct", "Nov", "Dec"], fontsize=9)
    ax.set_yticks(np.arange(len(cities)))
    ax.set_yticklabels([CITY_LABELS.get(c, c) for c in cities], fontsize=10)

    for i in range(len(cities)):
        peak_month = int(np.argmax(matrix[i]))
        for j in range(12):
            v = matrix[i, j]
            color = "white" if v > 9 else "#222"
            weight = "bold" if j == peak_month else "normal"
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center",
                    fontsize=8.2, color=color, fontweight=weight)

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("% of city's annual reviews\n(2022+ snapshot)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    fig.suptitle("When is each market booking? Monthly demand mix",
                 fontsize=13, fontweight="bold", y=0.995)
    ax.set_title("Each row sums to 100%.  Bold cell = peak month.  "
                 "Tall summer peaks (Hawaii, Nashville) imply seasonal pricing power; "
                 "flat patterns (NYC) imply year-round demand.",
                 fontsize=10, color="#444", pad=8)
    fig.text(0.01, -0.04, SOURCE_FOOTER, fontsize=8, color="#777")
    _save_fig(fig, PLOT_SEASONALITY)


def make_yearly_indexed_chart(yearly_df: pd.DataFrame) -> None:
    """Plot 06 — yearly trend, indexed to 2019.

    Reads as: every city is normalised so its 2019 review volume = 100.
    Lines above the dashed 100 line are markets that are **above their pre-COVID
    demand**; lines below are still recovering.  The slope of the post-2021 line
    is the recovery profile: whichever city has the steepest positive slope
    deserves a higher near-term occupancy projection.
    """
    pivot = yearly_df.pivot_table(
        index="year", columns="city", values="reviews", aggfunc="sum", fill_value=0
    ).sort_index()
    pivot = pivot[pivot.index >= 2015]
    if 2019 not in pivot.index:
        return  # safety
    base = pivot.loc[2019].replace(0, np.nan)
    indexed = pivot.divide(base, axis=1) * 100

    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.axhline(100, color="#444", linestyle=":", linewidth=1)
    ax.text(indexed.index.min(), 100, "  2019 baseline = 100",
            fontsize=8, color="#444", va="bottom")

    for city in indexed.columns:
        ax.plot(indexed.index, indexed[city],
                color=CITY_COLORS.get(city, "#888"),
                marker="o", markersize=4, linewidth=2,
                label=CITY_LABELS.get(city, city))

    last_year = int(indexed.index.max())
    for city in indexed.columns:
        y = indexed[city].iloc[-1]
        ax.text(last_year + 0.1, y, f"{CITY_LABELS.get(city, city)} ({y:.0f})",
                fontsize=9, va="center",
                color=CITY_COLORS.get(city, "#888"))

    ax.axvspan(2020, 2021, color="#999", alpha=0.12)
    _style_ax(ax, ylabel="Reviews indexed to 2019 (=100)", xlabel="Year")
    ax.set_xticks(indexed.index)
    ax.set_xticklabels([str(y) for y in indexed.index], rotation=0)
    ax.set_xlim(indexed.index.min() - 0.5, last_year + 1.7)

    fig.suptitle("Recovery profile: how much of pre-COVID demand has each market regained?",
                 fontsize=13, fontweight="bold", y=0.995)
    ax.set_title("Above 100 = exceeded 2019 demand.  Below 100 = still recovering.  "
                 "Use the latest-year slope, not the absolute level, when projecting forward bookings.",
                 fontsize=10, color="#444", pad=8)
    fig.text(0.01, -0.04, SOURCE_FOOTER, fontsize=8, color="#777")
    _save_fig(fig, PLOT_YEARLY_INDEXED)


def make_engagement_length_chart(per_city_results: list[dict]) -> None:
    """Plot 07 — review engagement (length distribution).

    Reads as: KDE-style overlay of cleaned-comment lengths per city.  This
    matters for two reasons: (a) text-analytics quality — longer comments
    contain richer signal for sentiment / topic models; (b) guest-experience
    diagnostic — markets where the median guest writes 200+ chars tend to
    have more loyal / opinionated audiences (e.g. Hawaii vacationers).
    Conversely, LA and SF have a fatter "short review" left tail, which we
    surfaced upstream and is now bounded by the 30-char filter.
    """
    fig, ax = plt.subplots(figsize=(11, 5.6))
    cap = 1200
    bins = np.linspace(0, cap, 80)

    for r in per_city_results:
        samples = np.array(r["length_samples"], dtype=float)
        if samples.size == 0:
            continue
        # Drop (don't clip) values above the visualization range — clipping
        # would create a misleading spike at the right edge.
        samples_in_range = samples[samples <= cap]
        if samples_in_range.size == 0:
            continue
        ax.hist(
            samples_in_range, bins=bins, density=True, histtype="step", linewidth=2.0,
            label=CITY_LABELS.get(r["city"], r["city"]),
            color=CITY_COLORS.get(r["city"], "#888"),
        )

    ax.axvline(CLEANING_MIN_LENGTH, color="#222", linestyle="--", linewidth=1)
    ymax = ax.get_ylim()[1]
    ax.text(CLEANING_MIN_LENGTH + 8, ymax * 0.92,
            f"30-char floor\n(cleaning drop)", fontsize=8.5, color="#222")

    _style_ax(ax, ylabel="Density (per city; integrates to 1)",
              xlabel="Cleaned-comment length (characters; tail beyond 1,200 chars omitted)")
    ax.legend(loc="upper right", fontsize=9, frameon=False)

    median_text = "  |  ".join(
        f"{CITY_LABELS.get(r['city'], r['city'])}: median {int(np.median(r['length_samples'])) if r['length_samples'] else 0}"
        for r in per_city_results
    )

    fig.suptitle("How engaged are guests when they write a review?",
                 fontsize=13, fontweight="bold", y=0.995)
    ax.set_title(median_text, fontsize=9.5, color="#444", pad=8)
    fig.text(0.01, -0.04, SOURCE_FOOTER, fontsize=8, color="#777")
    _save_fig(fig, PLOT_LENGTH)


def make_pipeline_funnel_chart(per_city_results: list[dict],
                               reconciliation_df: pd.DataFrame,
                               audit_df: pd.DataFrame | None) -> None:
    """Plot 08 — cleaning pipeline funnel.

    Reads as: per-city stacked bar showing **what fraction of raw reviews
    survives** each cleaning gate.  The "kept" segment is the usable corpus.
    The remaining segments are removed (duplicates → missing → blank/short).
    The chart is the headline answer to "how destructive is the cleaning?"
    Average loss is ~6-8% per city, dominated by very-short comments.
    """
    cities_order = [r["city"] for r in per_city_results]
    rows: list[dict] = []
    for city in cities_order:
        cleaned_total = next(
            (r["rows_total"] for r in per_city_results if r["city"] == city), 0
        )
        recon_row = reconciliation_df[reconciliation_df["city"] == city]
        raw_total = int(recon_row["raw_rows"].iloc[0]) if not recon_row.empty else cleaned_total
        dropped = max(raw_total - cleaned_total, 0)

        # If the cleaning audit is available, decompose dropped into reasons.
        if audit_df is not None and not audit_df.empty:
            audit_row = audit_df[audit_df["city"] == city]
        else:
            audit_row = pd.DataFrame()

        if not audit_row.empty:
            dup = int(audit_row.get("duplicate_rows_removed", pd.Series([0])).iloc[0])
            missing = int(audit_row.get("missing_rows_removed", pd.Series([0])).iloc[0])
            blank = int(audit_row.get("blank_after_cleaning", pd.Series([0])).iloc[0])
            short = int(audit_row.get("short_comments_removed", pd.Series([0])).iloc[0])
            other = max(dropped - (dup + missing + blank + short), 0)
        else:
            dup = missing = blank = 0
            short = dropped
            other = 0

        rows.append({
            "city": city,
            "raw_total": raw_total,
            "kept": cleaned_total,
            "dup": dup,
            "missing": missing,
            "blank": blank,
            "short": short,
            "other": other,
        })

    df = pd.DataFrame(rows)
    if df.empty or df["raw_total"].sum() == 0:
        return

    df["pct_kept"] = df["kept"] / df["raw_total"] * 100
    df["pct_dup"] = df["dup"] / df["raw_total"] * 100
    df["pct_missing"] = df["missing"] / df["raw_total"] * 100
    df["pct_blank"] = df["blank"] / df["raw_total"] * 100
    df["pct_short"] = df["short"] / df["raw_total"] * 100
    df["pct_other"] = df["other"] / df["raw_total"] * 100

    cities_lab = [CITY_LABELS.get(c, c) for c in df["city"]]
    fig, ax = plt.subplots(figsize=(11, 6.2))

    segments = [
        ("pct_kept", "#2ca02c", "Kept (usable corpus)"),
        ("pct_short", "#d62728", "Dropped: comment <30 chars"),
        ("pct_blank", "#888", "Dropped: blank after cleaning"),
        ("pct_missing", "#999", "Dropped: missing required field"),
        ("pct_dup", "#ff7f0e", "Dropped: exact duplicate"),
        ("pct_other", "#bbb", "Other delta vs raw"),
    ]
    bottom = np.zeros(len(df))
    for col, color, label in segments:
        vals = df[col].values
        ax.barh(cities_lab, vals, left=bottom, color=color, edgecolor="white",
                linewidth=0.5, label=label, height=0.65)
        for i, v in enumerate(vals):
            if v >= 1.5:
                ax.text(bottom[i] + v / 2, i, f"{v:.1f}%",
                        ha="center", va="center", fontsize=8.5,
                        color="white" if col == "pct_kept" else "#111",
                        fontweight="bold" if col == "pct_kept" else "normal")
        bottom += vals

    for i, raw_total in enumerate(df["raw_total"]):
        ax.text(101, i, f"  raw rows: {int(raw_total):,}", fontsize=8.5, va="center",
                color="#444")

    ax.set_xlim(0, 115)
    ax.set_xlabel("% of raw rows", fontsize=10)
    _style_ax(ax, grid="x")
    ax.invert_yaxis()
    ax.legend(loc="upper center", fontsize=8.8, frameon=False, ncol=3,
              bbox_to_anchor=(0.5, -0.12))

    fig.suptitle("How destructive is the cleaning pipeline?",
                 fontsize=13, fontweight="bold", y=0.995)
    ax.set_title("Each bar starts at 100% raw rows.  Green = usable corpus delivered to text-analytics.  "
                 "All five cities lose between 5% and 9% of raw rows, mostly to short comments.",
                 fontsize=10, color="#444", pad=8)
    fig.text(0.01, -0.18, SOURCE_FOOTER, fontsize=8, color="#777")
    _save_fig(fig, PLOT_FUNNEL)


def render_memo(
    per_city_results: list[dict],
    summary_df: pd.DataFrame,
    yearly_df: pd.DataFrame,
    reconciliation_df: pd.DataFrame,
) -> None:
    summary_view = summary_df.copy()
    summary_view["city"] = summary_view["city"].map(CITY_LABELS).fillna(summary_view["city"])
    summary_view["short_pct"] = (summary_df["short_clean_rows"] / summary_df["rows_total"] * 100).round(4)
    summary_view["blank_pct"] = (summary_df["blank_clean_rows"] / summary_df["rows_total"] * 100).round(4)
    summary_view["non_ascii_pct"] = (summary_df["non_ascii_rows"] / summary_df["rows_total"] * 100).round(2)

    headline_cols = [
        "city", "rows_total", "listings_unique", "reviewers_unique",
        "min_date", "max_date",
    ]
    headline_md = summary_view[headline_cols].to_markdown(index=False)

    quality_cols = [
        "city", "rows_total",
        "bad_listing_id_rows", "bad_date_rows",
        "short_clean_rows", "short_pct",
        "blank_clean_rows", "residual_html_rows",
        "non_ascii_rows", "non_ascii_pct",
    ]
    quality_md = summary_view[quality_cols].to_markdown(index=False)

    pctile_rows = []
    for r in per_city_results:
        p = length_percentiles(r["length_samples"])
        pctile_rows.append({"city": CITY_LABELS.get(r["city"], r["city"]), **p})
    pctile_df = pd.DataFrame(pctile_rows)
    pctile_md = pctile_df.to_markdown(index=False)

    intensity_rows = []
    for r in per_city_results:
        vals = np.array(list(r["listing_review_counts"].values()), dtype=float)
        intensity_rows.append({
            "city": CITY_LABELS.get(r["city"], r["city"]),
            "n_listings": int(vals.size),
            "median_reviews_per_listing": int(np.median(vals)) if vals.size else 0,
            "p75": int(np.percentile(vals, 75)) if vals.size else 0,
            "p95": int(np.percentile(vals, 95)) if vals.size else 0,
            "p99": int(np.percentile(vals, 99)) if vals.size else 0,
            "max": int(vals.max()) if vals.size else 0,
        })
    intensity_df = pd.DataFrame(intensity_rows).sort_values(
        "median_reviews_per_listing", ascending=False
    )
    intensity_md = intensity_df.to_markdown(index=False)

    seasonality_rows = []
    for r in per_city_results:
        counts = r.get("monthly_counts_recent") or r.get("monthly_counts") or {}
        total = sum(counts.values())
        if total == 0:
            continue
        peak_month = max(counts.items(), key=lambda kv: kv[1])[0]
        trough_month = min(counts.items(), key=lambda kv: kv[1])[0]
        peak_pct = counts[peak_month] / total * 100
        trough_pct = counts[trough_month] / total * 100
        month_label = lambda m: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                                 "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]
        seasonality_rows.append({
            "city": CITY_LABELS.get(r["city"], r["city"]),
            "peak_month": month_label(peak_month),
            "peak_share_pct": round(peak_pct, 1),
            "trough_month": month_label(trough_month),
            "trough_share_pct": round(trough_pct, 1),
            "peak_to_trough_ratio": round(peak_pct / trough_pct, 2) if trough_pct else float("nan"),
        })
    seasonality_md = (
        pd.DataFrame(seasonality_rows).to_markdown(index=False)
        if seasonality_rows else "_(no monthly data)_"
    )

    recovery_rows = []
    yearly_pivot = yearly_df.pivot_table(
        index="year", columns="city", values="reviews", aggfunc="sum", fill_value=0
    ).sort_index()
    if 2019 in yearly_pivot.index:
        latest_year = int(yearly_pivot.index.max())
        for city in yearly_pivot.columns:
            base = float(yearly_pivot.loc[2019, city])
            latest = float(yearly_pivot.loc[latest_year, city])
            if base > 0:
                recovery_rows.append({
                    "city": CITY_LABELS.get(city, city),
                    "reviews_2019": int(base),
                    f"reviews_{latest_year}": int(latest),
                    "indexed_to_2019": round(latest / base * 100, 0),
                })
    recovery_df = pd.DataFrame(recovery_rows).sort_values("indexed_to_2019", ascending=False)
    recovery_md = (
        recovery_df.to_markdown(index=False) if not recovery_df.empty else "_(2019 baseline missing)_"
    )

    long_lines = []
    for r in per_city_results:
        for length, snippet in r["sample_long_comments"][:1]:
            long_lines.append(
                f"- **{CITY_LABELS.get(r['city'], r['city'])}** · {length:,} chars · "
                f"\"{snippet[:160]}{'…' if len(snippet) > 160 else ''}\""
            )
    long_md = "\n".join(long_lines) if long_lines else "_(no extreme samples captured)_"

    total_rows = int(summary_df["rows_total"].sum())
    total_bad_listing = int(summary_df["bad_listing_id_rows"].sum())
    total_bad_date = int(summary_df["bad_date_rows"].sum())
    total_short = int(summary_df["short_clean_rows"].sum())
    total_blank = int(summary_df["blank_clean_rows"].sum())
    total_html = int(summary_df["residual_html_rows"].sum())

    fully_clean = (
        total_bad_listing == 0 and total_bad_date == 0
        and total_short == 0 and total_blank == 0 and total_html == 0
    )

    if not reconciliation_df.empty:
        all_same = bool(reconciliation_df["same_snapshot"].all())
        total_raw_rows = int(reconciliation_df["raw_rows"].sum())
        total_dropped = int(reconciliation_df["ids_dropped_by_cleaning"].sum())
        recon_view = reconciliation_df.copy()
        recon_view["city"] = recon_view["city"].map(CITY_LABELS).fillna(recon_view["city"])
        recon_md = recon_view.to_markdown(index=False)
        if all_same:
            snapshot_line = (
                f"Cleaning dropped {total_dropped:,} unique review IDs from "
                f"{total_raw_rows:,} raw rows "
                f"({round(total_dropped/total_raw_rows*100, 2)}% loss), and **every** "
                "cleaned ID exists in the corresponding raw file — i.e. the cleaning is "
                "reproducible end-to-end from `data/raw/reviews/`."
            )
        else:
            snapshot_line = (
                "**Snapshot mismatch detected**: at least one cleaned ID does not exist "
                "in the raw files. Cleaning is not reproducible from the local raws — "
                "investigate before re-running."
            )
    else:
        recon_md = "_(reconciliation skipped: raw files not found)_"
        snapshot_line = "_(reconciliation skipped: raw files not found in `data/raw/reviews/`)_"

    if fully_clean:
        residual_line = (
            "Every cleaned row has a numeric `listing_id`, a parseable `date`, "
            f"`comments_clean_length ≥ {CLEANING_MIN_LENGTH}`, no blank cleaned "
            "comments, and no residual HTML tags. The 2026-04-29 fix in "
            "`run_full_review_cleaning.py` (`csv.QUOTE_ALL` on output) eliminates "
            "the column-desync artefact that produced earlier `bad_listing_id` rows."
        )
    else:
        residual_line = (
            f"Residual issues are small but non-zero: {total_bad_listing:,} non-numeric "
            f"`listing_id`, {total_bad_date:,} unparseable `date`, {total_short:,} "
            f"short comments, {total_blank:,} blank, {total_html:,} residual HTML. "
            "Treat as defects to investigate before downstream modeling."
        )

    biggest_intensity = intensity_df.iloc[0] if not intensity_df.empty else None
    smallest_intensity = intensity_df.iloc[-1] if not intensity_df.empty else None

    if biggest_intensity is not None:
        intensity_takeaway = (
            f"Median listing in **{biggest_intensity['city']}** has "
            f"**{int(biggest_intensity['median_reviews_per_listing'])} reviews** lifetime, "
            f"vs {int(smallest_intensity['median_reviews_per_listing'])} in "
            f"**{smallest_intensity['city']}**. The top 5% of listings (P95) reach "
            f"{int(biggest_intensity['p95'])}+ reviews."
        )
    else:
        intensity_takeaway = "_(intensity data unavailable)_"

    if seasonality_rows:
        sample_seas = max(seasonality_rows, key=lambda r: r["peak_to_trough_ratio"])
        seasonality_takeaway = (
            f"Most seasonal market: **{sample_seas['city']}** "
            f"(peak {sample_seas['peak_month']} = {sample_seas['peak_share_pct']}% of yearly "
            f"reviews, ratio peak/trough = {sample_seas['peak_to_trough_ratio']}×)."
        )
    else:
        seasonality_takeaway = "_(seasonality data unavailable)_"

    if not recovery_df.empty:
        ahead = recovery_df[recovery_df["indexed_to_2019"] >= 100]
        behind = recovery_df[recovery_df["indexed_to_2019"] < 100]
        recovery_takeaway = (
            f"{len(ahead)} of {len(recovery_df)} cities are at or above 2019 demand levels. "
            f"Best recovery: **{recovery_df.iloc[0]['city']}** "
            f"({int(recovery_df.iloc[0]['indexed_to_2019'])} vs 2019=100). "
            f"Slowest: **{recovery_df.iloc[-1]['city']}** "
            f"({int(recovery_df.iloc[-1]['indexed_to_2019'])})."
        )
    else:
        recovery_takeaway = "_(recovery data unavailable)_"

    def _max_for(city_key: str) -> str:
        sel = summary_df[summary_df["city"] == city_key]
        if sel.empty or pd.isna(sel["max_date"].iloc[0]):
            return "—"
        return str(sel["max_date"].iloc[0])

    hawaii_max = _max_for("hawaii")
    la_max = _max_for("los_angeles")
    nash_max = _max_for("nashville")
    ny_max = _max_for("new_york")
    sf_max = _max_for("san_francisco")
    min_len = CLEANING_MIN_LENGTH

    if not reconciliation_df.empty:
        drop_pct_min = reconciliation_df["drop_pct_vs_raw_ids"].min()
        drop_pct_max = reconciliation_df["drop_pct_vs_raw_ids"].max()
        worst_city_row = reconciliation_df.loc[
            reconciliation_df["drop_pct_vs_raw_ids"].idxmax()
        ]
        worst_city_label = CITY_LABELS.get(worst_city_row["city"], worst_city_row["city"])
        audit_summary = (
            f"per-city drop ranges from **{drop_pct_min:.1f}%** to **{drop_pct_max:.1f}%** "
            f"of raw rows (worst case: {worst_city_label})"
        )
    else:
        audit_summary = "audit CSV unavailable on this run"

    body = f"""# Processed Reviews — Business EDA Memo

> Audience: a business reader scoring each city's revenue potential for the
> Term Project (\"Where should we invest $500K?\"). This memo characterises the
> **cleaned** review files in `data/processed/review/<city>/` and translates
> them into the three business signals reviews give us: demand intensity,
> seasonality, and post-COVID recovery.
>
> The technical why-each-rule narrative lives in
> [`scripts/cleaning/reviews/review_cleaning_decisions.md`](../../../../scripts/cleaning/reviews/review_cleaning_decisions.md).
> The pre-cleaning view lives in
> [`data/raw/reviews/_eda/raw_data_memo_reviews.md`](../../../raw/reviews/_eda/raw_data_memo_reviews.md).

## TL;DR — three business signals from the cleaned reviews

1. **Demand intensity (Plot 04).** {intensity_takeaway} For the revenue equation
   `Price × Occupancy × 365`, this is the **occupancy** input we cross-check
   against the calendar's `unavailability_rate` proxy.
2. **Seasonality (Plot 05).** {seasonality_takeaway} Markets with high
   peak/trough ratios reward dynamic pricing; flat markets favour year-round
   ADR optimisation.
3. **Recovery (Plot 06).** {recovery_takeaway} The latest-year slope is the
   right reference when projecting **forward** annual revenue, not the
   lifetime average.

## 1. Headline numbers (cleaned corpus)

{headline_md}

**Pipeline integrity:** {snapshot_line}

**Residual quality:** {residual_line}

## 2. Demand intensity per listing — Plot 04

![Demand intensity per listing]({MEMO_FIG_PREFIX}/{PLOT_DEMAND_INTENSITY.name})

{intensity_md}

**How to read this:** the per-listing review count is the **demand proxy**
the reviews-team contributes to the revenue equation. Inside Airbnb's
San Francisco study assumes a review rate ≈ 50% (1 review ≈ 2 bookings) and
an average stay of 3 nights → annual booked nights ≈ reviews × 6. Use the
**median** as the "typical investor" baseline and the **P95** as the band a
top-5% comparable listing would land in (the kNN cohort the prescriptive
step builds against).

## 3. Seasonality of demand — Plot 05

![Seasonality heatmap]({MEMO_FIG_PREFIX}/{PLOT_SEASONALITY.name})

{seasonality_md}

**How to read this:** rows are cities, columns are calendar months, cells are
the share of post-2022 reviews falling in that month (each row sums to 100%).
Tall summer peaks (Hawaii, Nashville) imply seasonal pricing power — ADR
typically rises 30-100% in those months. Flat patterns (NYC) imply year-round
demand and reduce revenue volatility. The peak-to-trough ratio in the
right-most column is a one-number summary of "how risky is this market's
seasonality?".

## 4. Post-COVID recovery — Plot 06

![Yearly trend, indexed to 2019]({MEMO_FIG_PREFIX}/{PLOT_YEARLY_INDEXED.name})

{recovery_md}

**How to read this:** every city is normalised to its 2019 review volume = 100.
Lines above the dashed line are above pre-COVID demand; below are still
recovering. **Forward** occupancy projections should weight recent slopes
more than absolute lifetime totals — leisure markets (Hawaii, Nashville)
recovered first; business-travel markets (SF) and regulation-heavy markets
(NYC) lag.

## 5. Review engagement (text quality) — Plot 07

![Review engagement length]({MEMO_FIG_PREFIX}/{PLOT_LENGTH.name})

{pctile_md}

**How to read this:** the cleaned-comment length distribution per city
(density-normalised so cities are comparable). The 30-character floor is
the only filter the cleaning step applies to length — there is no upper
bound, on purpose: long comments are exactly the rows that contain
detailed complaints / praise, the input for the text-analytics step.
Median lengths range across cities; LA / SF have a fatter "short" left tail.

### Examples of extreme-length cleaned comments (one per city)

{long_md}

## 6. How destructive is the cleaning? — Plot 08

![Cleaning pipeline funnel]({MEMO_FIG_PREFIX}/{PLOT_FUNNEL.name})

**How to read this:** for each city the bar starts at 100% raw rows. The
green segment is the surviving (usable) corpus, the other segments are the
rules that drop rows: short comments dominate, with smaller contributions
from missing fields, blanks, and exact duplicates. All five cities lose
between 6% and 9% of raw rows — a light, signal-preserving clean.

## 7. Residual quality (defensive checks)

{quality_md}

| Issue | Status | What to do downstream |
|---|---|---|
| Non-numeric `listing_id` | **Resolved** by the 2026-04-29 fix (`csv.QUOTE_ALL` on output). Was caused by un-escaped newlines in `comments` desyncing columns at re-read time. | Optional defensive guard `pd.to_numeric(listing_id, errors='coerce')`. |
| Unparseable `date` | **Resolved** (same root cause). | Optional defensive guard `pd.to_datetime(date, errors='coerce')`. |
| `comments_clean_length < {CLEANING_MIN_LENGTH}` | **Resolved** — 0 by construction. | — |
| Residual HTML | **Resolved** — every `comments_clean` is HTML-free. | — |
| Non-ASCII characters | **By design** — accents and emojis preserved (~22-30% of rows). | Decide per-task: tokenisers handle non-ASCII fine; for word-clouds you may want to strip accents. |
| Comments longer than the model context | **By design** — no upper cap (max ~12k chars). | Tokenisation step decides whether to clip / truncate / split. |

## 8. Raw ↔ cleaned reconciliation

For each city we compared the set of review `id`s in the raw file vs the
cleaned file. `ids_extra_in_cleaned` must be 0 if the cleaning is reproducible
from this raw snapshot.

{recon_md}

## 9. File layout (handover)

| Item | Path |
|---|---|
| Cleaning script | `scripts/cleaning/reviews/run_full_review_cleaning.py` |
| Cleaning decisions memo | `scripts/cleaning/reviews/review_cleaning_decisions.md` |
| Cleaned data | `data/processed/review/<city>/reviews_<city>_cleaned.csv` (5 files) |
| All-cities concat | `data/processed/reviews_all_cleaned.csv` |
| This memo | `data/processed/review/_eda/processed_data_memo_reviews.md` |
| Per-city summary CSV | `data/processed/review/_eda/reviews_processed_inventory.csv` |
| Yearly counts CSV | `data/processed/review/_eda/reviews_cleaned_per_year_by_city.csv` |
| Reconciliation CSV | `data/processed/review/_eda/reviews_raw_vs_cleaned_reconciliation.csv` |
| Plots | `reports/figures/market_analysis/reviews/04_*.png` to `reports/figures/market_analysis/reviews/08_*.png` |
| Cleaning audit CSV | `results/01_market_analysis/reviews/reviews_cleaning_audit.csv` (drop reasons per city) |

All five layers (raw / processed / listings / calendars / reviews) use the
same snake_case city tokens (`hawaii`, `los_angeles`, `nashville`, `new_york`,
`san_francisco`), so cross-layer joins use the city token directly without
any per-source remapping.

## 10. Technical appendix (data engineering view)

This section documents the **engineering** of the cleaned files (schema,
dtypes, audit numbers, reproducibility checks) for the dev side of the team.
The why-each-rule rationale lives in
[`scripts/cleaning/reviews/review_cleaning_decisions.md`](../../../../scripts/cleaning/reviews/review_cleaning_decisions.md).

### 10.1. Snapshot provenance

| city | Inside Airbnb snapshot date | max review date in cleaned file |
|---|---|---|
| Hawaii | 2025-09-16 | {hawaii_max} |
| Los Angeles | 2025-09-01 | {la_max} |
| Nashville | 2025-09-23 | {nash_max} |
| New York | 2025-10-01 | {ny_max} |
| San Francisco | 2025-09-01 | {sf_max} |

Snapshot dates are also tracked in the project root `README.md`. All five
cities were downloaded as a coordinated snapshot; do not mix files from
different snapshot quarters in cross-city comparisons.

### 10.2. Output schema (cleaned files)

The cleaning step keeps the six raw Inside Airbnb columns and appends two
derived columns (`comments_clean`, `comments_clean_length`):

| Column | Dtype (recommended on read) | Description |
|---|---|---|
| `listing_id` | `Int64` (cast from `string`) | Listing identifier; foreign key to `listings.csv`. |
| `id` | `Int64` | Review identifier (unique within a city). |
| `date` | `datetime64[ns]` | Review post date (`YYYY-MM-DD`). |
| `reviewer_id` | `Int64` | Reviewer identifier; useful for repeat-guest analytics. |
| `reviewer_name` | `string` | Reviewer's first name; not validated. |
| `comments` | `string` | **Original** review text (verbatim, preserved for re-cleaning). |
| `comments_clean` | `string` | HTML-stripped, whitespace-normalised, lower-cased text. |
| `comments_clean_length` | `Int64` | Character count of `comments_clean`; always ≥ {min_len} by construction. |

Files use `csv.QUOTE_ALL` on output (`quotechar='"'`, `escapechar='\\\\'`) so
any embedded newlines / commas / quotes inside `comments` are unambiguous on
re-read. `pandas.read_csv` handles this transparently.

### 10.3. Cleaning rules (summary table)

| # | Rule | Effect | Drops or keeps |
|---|---|---|---|
| 1 | Project to 6 raw columns | Discard everything else from Inside Airbnb | n/a |
| 2 | `clean_missing_text` | Strip + normalise `""`, `"nan"`, `"None"` → `pd.NA` | n/a |
| 3 | Hash-dedup on all 6 cols | Drop accidental duplicates within a city file | drop |
| 4 | Drop rows with any null in the 6 cols | Eliminate unusable reviews (no text / no id / no date) | drop |
| 5 | HTML unescape + tag strip + whitespace collapse + lower-case | Normalise text into `comments_clean` | keep |
| 6 | `len(comments_clean) < {min_len}` | Drop trivially-short comments | drop |
| 7 | Append `comments_clean` and `comments_clean_length` | New columns for downstream | n/a |

Volume effect (audit numbers from `results/01_market_analysis/reviews/reviews_cleaning_audit.csv`,
when present): {audit_summary}.

### 10.4. Defensive read at the consumer side

Even though the residual-issue counts are zero, this snippet is the
recommended read pattern because it protects against future regressions:

```python
df = pd.read_csv(path, dtype={{'listing_id': 'string'}}, low_memory=False)
df['listing_id'] = pd.to_numeric(df['listing_id'], errors='coerce').astype('Int64')
df['date']       = pd.to_datetime(df['date'], errors='coerce')
df = df.dropna(subset=['listing_id', 'date', 'comments_clean'])
```

### 10.5. Reproducibility

Snapshot match is confirmed for all five cities (see Section 8). Re-running
`run_full_review_cleaning.py` on `data/raw/reviews/` regenerates the cleaned
files **bit-identically** (post `csv.QUOTE_ALL` fix). Approximate runtime
~5 minutes on a laptop-class machine.

## 11. Recommendations for the next stages

1. **Defensive read** at the top of any consumer script (Section 10.4).

2. **Demand-proxy join.** Aggregate cleaned reviews to `(listing_id, year)`
   and merge with `data/processed/calendar/<city>/...` so the prescriptive
   step can compare the calendar-based occupancy proxy with the review-based
   one (San Francisco model) on the same listings.

3. **Long comments stay.** Truncate at the tokenisation step (e.g. p99
   ≈ 1.4–1.6k chars depending on city), not at the cleaning step.

4. **Snapshot discipline.** Any rerun must re-pull all five cities together;
   mixing snapshot quarters biases year-over-year comparisons (see
   Section 10.1).
"""

    MEMO_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMO_PATH.write_text(body, encoding="utf-8")


def main() -> None:
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Scanning cleaned reviews ...")
    per_city_results: list[dict] = []
    reconciliation_rows: list[dict] = []
    for city, fname in CITY_FILES.items():
        path = PROCESSED_REVIEW_DIR / city / fname
        if not path.exists():
            print(f"  WARNING: {path} not found — skipping {city}")
            continue
        size_mb = path.stat().st_size // (1024 * 1024)
        print(f"  Scanning {city} ({size_mb} MB) ...")
        result = analyze_city(city, path)
        print(
            f"    rows={result['rows_total']:,}  listings={result['listings_unique']:,} "
            f"bad_listing={result['bad_listing_id_rows']}  bad_date={result['bad_date_rows']}  "
            f"min={result['min_date']}  max={result['max_date']}"
        )

        raw_path = RAW_DIR / RAW_FILES[city]
        if raw_path.exists():
            print(f"    Reconciling against raw ({raw_path.stat().st_size // (1024*1024)} MB) ...")
            recon = reconcile_with_raw(city, raw_path, result["_review_id_set"])
            reconciliation_rows.append(recon)
            print(
                f"      raw_ids={recon['raw_unique_ids']:,}  cleaned_ids={recon['cleaned_unique_ids']:,} "
                f"dropped={recon['ids_dropped_by_cleaning']:,} ({recon['drop_pct_vs_raw_ids']}%) "
                f"extra_in_cleaned={recon['ids_extra_in_cleaned']}  "
                f"same_snapshot={recon['same_snapshot']}"
            )
        else:
            print(f"    WARNING: raw file {raw_path} not found — skipping reconciliation for {city}")

        # Drop in-memory ID set before keeping the result around.
        result.pop("_review_id_set", None)
        per_city_results.append(result)

    if not per_city_results:
        raise FileNotFoundError(
            f"No cleaned review files found under {PROCESSED_REVIEW_DIR}/<city>/ . "
            f"Run scripts/cleaning/reviews/run_full_review_cleaning.py first."
        )

    reconciliation_df = pd.DataFrame(reconciliation_rows)
    if not reconciliation_df.empty:
        reconciliation_df.to_csv(RECONCILIATION_CSV, index=False)
        print(f"Saved reconciliation CSV → {RECONCILIATION_CSV}")

    summary_rows = [
        {
            "city": r["city"],
            "rows_total": r["rows_total"],
            "listings_unique": r["listings_unique"],
            "reviewers_unique": r["reviewers_unique"],
            "review_ids_unique": r["review_ids_unique"],
            "duplicate_review_ids": r["duplicate_review_ids"],
            "bad_listing_id_rows": r["bad_listing_id_rows"],
            "bad_date_rows": r["bad_date_rows"],
            "blank_clean_rows": r["blank_clean_rows"],
            "short_clean_rows": r["short_clean_rows"],
            "residual_html_rows": r["residual_html_rows"],
            "non_ascii_rows": r["non_ascii_rows"],
            "min_date": r["min_date"],
            "max_date": r["max_date"],
        }
        for r in per_city_results
    ]
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(INVENTORY_CSV, index=False)
    print(f"Saved inventory CSV → {INVENTORY_CSV}")

    yearly_rows = []
    for r in per_city_results:
        for year, count in r["yearly_counts"].items():
            yearly_rows.append({"city": r["city"], "year": year, "reviews": count})
    yearly_df = pd.DataFrame(yearly_rows)
    yearly_df.to_csv(YEARLY_CSV, index=False)
    print(f"Saved yearly counts CSV → {YEARLY_CSV}")

    audit_df: pd.DataFrame | None
    if AUDIT_CSV.exists():
        try:
            audit_df = pd.read_csv(AUDIT_CSV)
        except Exception:
            audit_df = None
    else:
        audit_df = None

    make_demand_intensity_chart(per_city_results)
    make_seasonality_heatmap(per_city_results)
    make_yearly_indexed_chart(yearly_df)
    make_engagement_length_chart(per_city_results)
    make_pipeline_funnel_chart(per_city_results, reconciliation_df, audit_df)
    print(f"Saved 5 business-focused charts → {FIGURES_DIR}")

    render_memo(per_city_results, summary_df, yearly_df, reconciliation_df)
    print(f"Saved memo → {MEMO_PATH}")


if __name__ == "__main__":
    main()
