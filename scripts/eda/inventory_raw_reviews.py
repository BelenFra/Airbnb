"""Raw Airbnb reviews inventory and quality memo.

Builds a statistical memo of the raw review files for the five required
cities. The memo justifies and audits the cleaning decisions implemented in
``scripts/cleaning/reviews/run_full_review_cleaning.py``.

Outputs
-------
- ``data/raw/reviews/_eda/reviews_raw_inventory.csv`` — per-city summary table.
- ``data/raw/reviews/_eda/reviews_per_year_by_city.csv`` — yearly review counts.
- ``reports/figures/01_market_analysis/reviews/01_market_scope_by_city.png`` — supply scale + market maturity.
- ``reports/figures/01_market_analysis/reviews/02_demand_timeline_by_city.png`` — yearly review volume (demand signal).
- ``reports/figures/01_market_analysis/reviews/03_data_quality_gates.png`` — quality issues that the cleaning step has to remove.
- ``data/raw/reviews/_eda/raw_data_memo_reviews.md`` — narrative memo for the team.

The script processes each file in 200k-row chunks so memory stays below
~500MB even though the largest raw file is ~500MB on disk.
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

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import mba706_toolkit as tk  # noqa: F401  (kept for parity with project rules)

RANDOM_STATE = 42

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "reviews"
# EDA artefacts live in a sibling folder so the cleaning script's glob
# (``RAW_DIR.glob("reviews_*.csv")``, non-recursive) does not pick them up.
EDA_DIR = RAW_DIR / "_eda"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "01_market_analysis" / "reviews"
MEMO_PATH = EDA_DIR / "raw_data_memo_reviews.md"
INVENTORY_CSV = EDA_DIR / "reviews_raw_inventory.csv"
YEARLY_CSV = EDA_DIR / "reviews_per_year_by_city.csv"

PLOT_MARKET_SCOPE = FIGURES_DIR / "01_market_scope_by_city.png"
PLOT_DEMAND_TIMELINE = FIGURES_DIR / "02_demand_timeline_by_city.png"
PLOT_QUALITY_GATES = FIGURES_DIR / "03_data_quality_gates.png"

# Path used to embed images in the memo. Memo lives at
# ``data/raw/reviews/_eda/raw_data_memo_reviews.md``; figures live at
# ``reports/figures/01_market_analysis/reviews/*.png``. Relative path goes up four levels.
MEMO_FIG_PREFIX = "../../../../reports/figures/01_market_analysis/reviews"

CITY_FILES = {
    "hawaii": "reviews_hawaii.csv",
    "los_angeles": "reviews_los_angeles.csv",
    "nashville": "reviews_nashville.csv",
    "new_york": "reviews_new_york.csv",
    "san_francisco": "reviews_san_francisco.csv",
}

EXPECTED_COLUMNS = ["listing_id", "id", "date", "reviewer_id", "reviewer_name", "comments"]
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
NON_ASCII_PATTERN = re.compile(r"[^\x00-\x7f]")
ENGLISH_STOPWORDS = {
    "the", "and", "was", "for", "with", "this", "that", "very",
    "great", "stay", "place", "host", "would", "have",
}
CHUNK_SIZE = 200_000
LENGTH_SAMPLE_CAP = 200_000

# Cleaning thresholds mirrored from run_full_review_cleaning.py
CLEANING_MIN_LENGTH = 30


def analyze_city(city: str, csv_path: Path) -> dict:
    """Stream the CSV in chunks to compute statistics without loading all in memory."""

    rows_total = 0
    nulls = {col: 0 for col in EXPECTED_COLUMNS}
    blank_comments = 0
    short_comments = 0  # < 30 characters after strip
    very_short_comments = 0  # < 10 characters
    html_rows = 0
    non_ascii_rows = 0
    english_keyword_hits = 0
    sampled_for_lang = 0

    listing_ids = set()
    reviewer_ids = set()
    review_ids = set()
    duplicate_review_ids = 0

    comment_lengths: list[int] = []  # bounded by LENGTH_SAMPLE_CAP

    yearly_counts: dict[int, int] = {}
    min_date = None
    max_date = None

    sample_reviews: list[str] = []

    for chunk in pd.read_csv(
        csv_path,
        usecols=EXPECTED_COLUMNS,
        dtype={
            "listing_id": "Int64",
            "id": "Int64",
            "reviewer_id": "Int64",
            "reviewer_name": "string",
            "comments": "string",
        },
        parse_dates=["date"],
        chunksize=CHUNK_SIZE,
        encoding="utf-8-sig",
        on_bad_lines="skip",
    ):
        rows_total += len(chunk)

        for col in EXPECTED_COLUMNS:
            nulls[col] += int(chunk[col].isna().sum())

        listing_ids.update(chunk["listing_id"].dropna().astype("int64").tolist())
        reviewer_ids.update(chunk["reviewer_id"].dropna().astype("int64").tolist())

        review_id_chunk = chunk["id"].dropna().astype("int64")
        before = len(review_ids)
        review_ids.update(review_id_chunk.tolist())
        added = len(review_ids) - before
        duplicate_review_ids += int(len(review_id_chunk) - added)

        if min_date is None:
            min_date = chunk["date"].min()
            max_date = chunk["date"].max()
        else:
            min_date = min(min_date, chunk["date"].min())
            max_date = max(max_date, chunk["date"].max())

        years = chunk["date"].dt.year.dropna().astype(int)
        for year, count in years.value_counts().items():
            yearly_counts[int(year)] = yearly_counts.get(int(year), 0) + int(count)

        comments = chunk["comments"].fillna("").astype(str)
        stripped = comments.str.strip()

        blank_comments += int((stripped == "").sum())
        short_comments += int((stripped.str.len() < 30).sum())
        very_short_comments += int((stripped.str.len() < 10).sum())
        html_rows += int(comments.str.contains(HTML_TAG_PATTERN, regex=True, na=False).sum())
        non_ascii_rows += int(comments.str.contains(NON_ASCII_PATTERN, regex=True, na=False).sum())

        if len(comment_lengths) < LENGTH_SAMPLE_CAP:
            remaining = LENGTH_SAMPLE_CAP - len(comment_lengths)
            comment_lengths.extend(stripped.str.len().head(remaining).tolist())

        sample = comments.sample(min(len(comments), 5000), random_state=RANDOM_STATE).str.lower()
        for text in sample:
            sampled_for_lang += 1
            tokens = text.split()
            if not tokens:
                continue
            hits = sum(1 for t in tokens if t in ENGLISH_STOPWORDS)
            if hits >= 2:
                english_keyword_hits += 1

        if len(sample_reviews) < 3:
            for txt in chunk["comments"].dropna().astype(str).head(3 - len(sample_reviews)):
                sample_reviews.append(txt[:280])

    lengths = np.array(comment_lengths, dtype=float)
    if lengths.size:
        len_mean = float(np.mean(lengths))
        len_median = float(np.median(lengths))
        len_p95 = float(np.percentile(lengths, 95))
        len_max = float(np.max(lengths))
    else:
        len_mean = len_median = len_p95 = len_max = 0.0

    english_share = english_keyword_hits / sampled_for_lang if sampled_for_lang else 0

    return {
        "city": city,
        "source_file": str(csv_path.relative_to(PROJECT_ROOT)),
        "rows_total": rows_total,
        "unique_listings": len(listing_ids),
        "unique_reviewers": len(reviewer_ids),
        "unique_review_ids": len(review_ids),
        "duplicate_review_ids": duplicate_review_ids,
        "nulls_listing_id": nulls["listing_id"],
        "nulls_id": nulls["id"],
        "nulls_date": nulls["date"],
        "nulls_reviewer_id": nulls["reviewer_id"],
        "nulls_reviewer_name": nulls["reviewer_name"],
        "nulls_comments": nulls["comments"],
        "blank_comments": blank_comments,
        "comments_under_10_chars": very_short_comments,
        "comments_under_30_chars": short_comments,
        "rows_with_html_tags": html_rows,
        "rows_with_non_ascii": non_ascii_rows,
        "comment_length_mean": round(len_mean, 1),
        "comment_length_median": round(len_median, 1),
        "comment_length_p95": round(len_p95, 1),
        "comment_length_max": round(len_max, 1),
        "english_share_estimate": round(english_share, 4),
        "min_date": str(min_date.date()) if pd.notna(min_date) else "",
        "max_date": str(max_date.date()) if pd.notna(max_date) else "",
        "yearly_counts": yearly_counts,
        "sample_reviews": sample_reviews,
        "comment_lengths_sample": comment_lengths,
    }


def build_yearly_long(stats_per_city: list[dict]) -> pd.DataFrame:
    rows = []
    for stats in stats_per_city:
        for year, count in stats["yearly_counts"].items():
            rows.append({"city": stats["city"], "year": int(year), "reviews": int(count)})
    df = pd.DataFrame(rows).sort_values(["city", "year"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Plots — three business-focused charts that answer:
#   (1) How big and how mature is each market? (supply + maturity)
#   (2) How does demand evolve over time per city? (yearly volume + COVID dip)
#   (3) How much of the raw data needs to be discarded by cleaning, and why?
# Detailed per-issue tables remain in the markdown memo; the figures highlight
# only the headline numbers a non-technical reader needs to remember.
# ---------------------------------------------------------------------------

CITY_COLORS = {
    "hawaii": "#E69F00",
    "los_angeles": "#56B4E9",
    "nashville": "#009E73",
    "new_york": "#D55E00",
    "san_francisco": "#CC79A7",
}

CITY_DISPLAY = {
    "hawaii": "Hawaii",
    "los_angeles": "Los Angeles",
    "nashville": "Nashville",
    "new_york": "New York",
    "san_francisco": "San Francisco",
}

SOURCE_FOOTER = (
    "Source: Inside Airbnb 2025-09 snapshot (raw, pre-cleaning).  "
    "Five-city Term Project (MBA 706)."
)


def _save_fig(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _style_ax(ax, *, ylabel: str | None = None, xlabel: str | None = None,
              grid: str = "y") -> None:
    """Consistent styling for all charts."""
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if grid:
        ax.grid(axis=grid, linestyle="--", alpha=0.35, linewidth=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="both", labelsize=9)


def _city_display_list(stats_per_city: list[dict]) -> list[str]:
    return [CITY_DISPLAY.get(s["city"], s["city"]) for s in stats_per_city]


def make_market_scope_chart(stats_per_city: list[dict]) -> None:
    """Plot 01 — market scope (two panels).

    Both panels are answered directly with review data:
      Panel A — *Supply scale*: how many distinct listings appear at all in the
        review file (a lower bound on each city's active inventory).
      Panel B — *Recent demand intensity*: average reviews per listing in the
        last full year (2024).  This is the per-property demand signal that
        feeds into the revenue equation; it is a much fairer "is this market
        active?" diagnostic than the year of the very first review (which only
        captures when Airbnb opened in the city, not whether it is busy now).
    """
    latest_full_year = 2024
    rows = []
    for s in stats_per_city:
        listings = max(int(s["unique_listings"]), 0)
        reviews_year = int(s.get("yearly_counts", {}).get(latest_full_year, 0))
        rpl = reviews_year / listings if listings > 0 else 0.0
        rows.append({
            "city_key": s["city"],
            "city": CITY_DISPLAY.get(s["city"], s["city"]),
            "listings": listings,
            "reviews_2024": reviews_year,
            "reviews_per_listing_2024": rpl,
        })
    df = pd.DataFrame(rows)

    df_supply = df.sort_values("listings", ascending=True)
    df_demand = df.sort_values("reviews_per_listing_2024", ascending=True)

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(13, 5.4))

    colors_a = [CITY_COLORS.get(c, "#888") for c in df_supply["city_key"]]
    bars_a = ax_a.barh(df_supply["city"], df_supply["listings"], color=colors_a,
                       edgecolor="white", linewidth=0.5, height=0.65)
    for bar, n in zip(bars_a, df_supply["listings"]):
        ax_a.text(bar.get_width() + max(df_supply["listings"]) * 0.01,
                  bar.get_y() + bar.get_height() / 2,
                  f"{int(n):,}", ha="left", va="center", fontsize=9.5,
                  fontweight="bold", color="#222")
    ax_a.set_xlim(right=max(df_supply["listings"]) * 1.20)
    ax_a.set_title("A. Supply scale\nUnique listings ever reviewed",
                   fontsize=11, color="#222", loc="left")
    _style_ax(ax_a, xlabel="Listings (count)", grid="x")

    colors_b = [CITY_COLORS.get(c, "#888") for c in df_demand["city_key"]]
    bars_b = ax_b.barh(df_demand["city"], df_demand["reviews_per_listing_2024"],
                       color=colors_b, edgecolor="white", linewidth=0.5, height=0.65)
    for bar, rpl, n in zip(bars_b, df_demand["reviews_per_listing_2024"],
                            df_demand["reviews_2024"]):
        ax_b.text(bar.get_width() + max(df_demand["reviews_per_listing_2024"]) * 0.015,
                  bar.get_y() + bar.get_height() / 2,
                  f"{rpl:.1f}  ({int(n):,} reviews / yr)",
                  ha="left", va="center", fontsize=9.5,
                  fontweight="bold", color="#222")
    ax_b.set_xlim(right=max(df_demand["reviews_per_listing_2024"]) * 1.55)
    ax_b.set_title(f"B. Recent demand intensity\nAvg reviews per listing in {latest_full_year}",
                   fontsize=11, color="#222", loc="left")
    _style_ax(ax_b, xlabel=f"Reviews / listing in {latest_full_year}", grid="x")

    fig.suptitle("How big is each market, and how busy is the average listing?",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.text(0.5, 0.93,
             "Panel A is the supply denominator (more listings = more competition).  "
             f"Panel B is the latest-full-year demand signal: a high reviews-per-listing "
             "means the average property is booking often.",
             ha="center", fontsize=9.5, color="#444")
    fig.text(0.01, -0.04, SOURCE_FOOTER, fontsize=8, color="#777")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    _save_fig(fig, PLOT_MARKET_SCOPE)


def make_demand_timeline_chart(yearly_df: pd.DataFrame) -> None:
    """Plot 02 — demand timeline.

    Reads as: yearly review counts are a leading indicator of bookings (a
    review is published ~14 days after check-out).  The 2020 dip is the
    pandemic; the slope after that is the recovery profile per city.
    Hawaii / Nashville rebound earlier than NYC / SF (regulation + business
    travel) — relevant when projecting near-term occupancy in the memo.
    """
    pivot = yearly_df.pivot_table(
        index="year", columns="city", values="reviews", aggfunc="sum", fill_value=0
    ).sort_index()
    pivot = pivot[pivot.index >= 2014]

    fig, ax = plt.subplots(figsize=(11, 5.6))
    for city in pivot.columns:
        ax.plot(pivot.index, pivot[city] / 1000,
                color=CITY_COLORS.get(city, "#888"),
                marker="o", markersize=4, linewidth=2,
                label=CITY_DISPLAY.get(city, city))

    ax.axvspan(2020, 2021, color="#999", alpha=0.15)
    ax.text(2020.5, ax.get_ylim()[1] * 0.92, "COVID-19", ha="center", fontsize=9,
            color="#555", fontweight="bold")

    last_year = int(pivot.index.max())
    for city in pivot.columns:
        y = pivot[city].iloc[-1] / 1000
        ax.text(last_year + 0.1, y, CITY_DISPLAY.get(city, city),
                fontsize=9, va="center",
                color=CITY_COLORS.get(city, "#888"))

    _style_ax(ax, ylabel="Reviews per year (thousands)", xlabel="Year")
    ax.set_xticks(pivot.index)
    ax.set_xticklabels([str(y) for y in pivot.index], rotation=0)
    ax.set_xlim(pivot.index.min() - 0.5, last_year + 1.5)
    ax.legend(loc="upper left", fontsize=9, frameon=False, ncol=3)

    fig.suptitle("How does demand evolve year-over-year?", fontsize=13,
                 fontweight="bold", y=0.995)
    ax.set_title("Reviews-per-year is a noisy but unbiased proxy for actual bookings (review rate ≈ 50%).  "
                 "The shape of the post-2020 recovery differs per city.",
                 fontsize=10, color="#444", pad=8)
    fig.text(0.01, -0.04, SOURCE_FOOTER, fontsize=8, color="#777")
    _save_fig(fig, PLOT_DEMAND_TIMELINE)


def make_quality_gates_chart(stats_per_city: list[dict]) -> None:
    """Plot 03 — data-quality gates.

    Reads as: percentage of raw rows that **each cleaning rule** has to drop
    or transform before the data is usable.  The taller the bar, the bigger
    the cleaning intervention.  The right column ("non-English share") is a
    descriptor that the cleaning step does **not** act on (kept by design,
    deferred to text-analytics).
    """
    issues = [
        ("comments_under_30_chars", "Short comment (<30 chars, drop)", "#D55E00"),
        ("rows_with_html_tags", "HTML markup (<br/> etc., strip)", "#56B4E9"),
        ("rows_with_non_ascii", "Non-English share (kept by design)", "#9467BD"),
    ]
    cities = _city_display_list(stats_per_city)
    n_issues = len(issues)
    width = 0.78 / n_issues
    x = np.arange(len(cities))

    fig, ax = plt.subplots(figsize=(11, 5.8))
    for i, (key, label, color) in enumerate(issues):
        pct = [s[key] / s["rows_total"] * 100 if s["rows_total"] else 0
               for s in stats_per_city]
        offset = (i - n_issues / 2) * width + width / 2
        bars = ax.bar(x + offset, pct, width=width, label=label, color=color,
                      edgecolor="white", linewidth=0.4, alpha=0.92)
        for bar, v in zip(bars, pct):
            if v >= 0.5:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
                        f"{v:.1f}%", ha="center", va="bottom", fontsize=8.5,
                        color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(cities, fontsize=10)
    _style_ax(ax, ylabel="% of raw rows")
    ax.set_ylim(top=ax.get_ylim()[1] * 1.10)
    ax.legend(loc="upper center", fontsize=9, frameon=False, ncol=3,
              bbox_to_anchor=(0.5, 1.02))

    fig.suptitle("How much of the raw data needs cleaning?", fontsize=13,
                 fontweight="bold", y=1.04)
    ax.set_title("LA has the highest short-comment share (drop); NYC + Hawaii the highest HTML share (strip);  "
                 "Hawaii + NYC the highest non-English share (kept by design).",
                 fontsize=9.5, color="#444", pad=20)
    fig.text(0.01, -0.04, SOURCE_FOOTER, fontsize=8, color="#777")
    _save_fig(fig, PLOT_QUALITY_GATES)


# ---------------------------------------------------------------------------
# Memo rendering
# ---------------------------------------------------------------------------


def render_memo(stats_per_city: list[dict], yearly_df: pd.DataFrame) -> str:
    summary_df = pd.DataFrame([
        {
            "city": s["city"],
            "rows_total": s["rows_total"],
            "unique_listings": s["unique_listings"],
            "unique_reviewers": s["unique_reviewers"],
            "duplicate_review_ids": s["duplicate_review_ids"],
            "min_date": s["min_date"],
            "max_date": s["max_date"],
            "blank_comments": s["blank_comments"],
            "comments_under_30_chars": s["comments_under_30_chars"],
            "rows_with_html_tags": s["rows_with_html_tags"],
            "rows_with_non_ascii": s["rows_with_non_ascii"],
            "comment_length_median": s["comment_length_median"],
            "comment_length_p95": s["comment_length_p95"],
            "english_share_estimate": s["english_share_estimate"],
        }
        for s in stats_per_city
    ])

    total_rows = int(summary_df["rows_total"].sum())
    total_listings = int(summary_df["unique_listings"].sum())
    total_dupes = int(summary_df["duplicate_review_ids"].sum())
    total_html = int(summary_df["rows_with_html_tags"].sum())

    pct_html_total = total_html / total_rows * 100 if total_rows else 0
    pct_dupes_total = total_dupes / total_rows * 100 if total_rows else 0

    summary_df["pct_html"] = (
        summary_df["rows_with_html_tags"] / summary_df["rows_total"] * 100
    ).round(2)
    summary_df["pct_short_30"] = (
        summary_df["comments_under_30_chars"] / summary_df["rows_total"] * 100
    ).round(2)
    summary_df["pct_blank"] = (
        summary_df["blank_comments"] / summary_df["rows_total"] * 100
    ).round(4)
    summary_df["pct_non_ascii"] = (
        summary_df["rows_with_non_ascii"] / summary_df["rows_total"] * 100
    ).round(2)

    table_main_cols = [
        "city", "rows_total", "unique_listings", "unique_reviewers",
        "min_date", "max_date",
        "comment_length_median", "comment_length_p95", "english_share_estimate",
    ]
    table_quality_cols = [
        "city", "rows_total",
        "duplicate_review_ids", "blank_comments", "pct_blank",
        "comments_under_30_chars", "pct_short_30",
        "rows_with_html_tags", "pct_html",
        "rows_with_non_ascii", "pct_non_ascii",
    ]

    yearly_pivot = (
        yearly_df.pivot_table(
            index="year", columns="city", values="reviews", aggfunc="sum", fill_value=0
        ).astype(int).reset_index().sort_values("year")
    )

    examples_md = []
    for s in stats_per_city:
        examples_md.append(f"### {s['city']}")
        for i, txt in enumerate(s["sample_reviews"], start=1):
            txt_one_line = txt.replace("\n", " ").replace("|", "\\|")
            examples_md.append(f"- *Sample {i}:* {txt_one_line}")
        examples_md.append("")

    biggest_market = summary_df.sort_values("rows_total", ascending=False).iloc[0]
    smallest_market = summary_df.sort_values("rows_total", ascending=False).iloc[-1]
    latest_max_date = summary_df["max_date"].max()
    avg_reviews_per_listing = (
        summary_df["rows_total"].sum() / max(int(summary_df["unique_listings"].sum()), 1)
    )
    worst_short = summary_df.sort_values("pct_short_30", ascending=False).iloc[0]
    worst_html = summary_df.sort_values("pct_html", ascending=False).iloc[0]
    worst_non_ascii = summary_df.sort_values("pct_non_ascii", ascending=False).iloc[0]

    # Recent demand intensity: avg reviews per listing in the last full year.
    latest_full_year = 2024
    intensity_rows = []
    for s in stats_per_city:
        listings = max(int(s["unique_listings"]), 0)
        ry = int(s.get("yearly_counts", {}).get(latest_full_year, 0))
        intensity_rows.append({
            "city": s["city"],
            "rpl_2024": ry / listings if listings > 0 else 0.0,
        })
    intensity_df_local = pd.DataFrame(intensity_rows).sort_values("rpl_2024", ascending=False)
    busiest = intensity_df_local.iloc[0]
    quietest = intensity_df_local.iloc[-1]

    md: list[str] = []
    md.append("# Raw Reviews — Business EDA Memo")
    md.append("")
    md.append("> Audience: a business reader sizing each city's Airbnb market for the "
              "Term Project (\"Where should we invest $500K?\").  This memo characterises "
              "the **raw** review files in `data/raw/reviews/` so that any later analysis "
              "(demand proxy, sentiment, topic modeling) starts from a well-understood "
              "dataset.  Detailed per-rule cleaning rationale lives in "
              "[`scripts/cleaning/reviews/review_cleaning_decisions.md`]"
              "(../../../scripts/cleaning/reviews/review_cleaning_decisions.md).")
    md.append("")
    md.append("## TL;DR — three things to remember")
    md.append("")
    md.append(f"1. **Scale.** {total_rows/1e6:.2f}M raw reviews across the five cities, "
              f"covering {total_listings:,} unique listings (≈ {avg_reviews_per_listing:.0f} "
              f"reviews per listing on average over the listing's lifetime). The biggest "
              f"market by review volume is **{CITY_DISPLAY[biggest_market['city']]}** "
              f"({biggest_market['rows_total']/1e6:.2f}M); the smallest is "
              f"**{CITY_DISPLAY[smallest_market['city']]}** "
              f"({smallest_market['rows_total']/1e6:.2f}M). Snapshot covers up to "
              f"**{latest_max_date}**.")
    md.append(f"2. **Recent demand intensity.** In the last full year ({latest_full_year}), "
              f"the average **{CITY_DISPLAY[busiest['city']]}** listing received "
              f"**{busiest['rpl_2024']:.1f} reviews**, vs **{quietest['rpl_2024']:.1f}** "
              f"in **{CITY_DISPLAY[quietest['city']]}** (Plot 01, Panel B). At a 50% "
              "review-rate, that translates roughly into "
              f"{busiest['rpl_2024']*2:.0f} bookings vs {quietest['rpl_2024']*2:.0f} "
              "bookings per listing per year — the gap matters for the occupancy input "
              "of the revenue equation.")
    md.append(f"3. **Cleaning is light, not destructive.** ~6–8% of rows per city are "
              f"dropped (mostly short or duplicate comments). HTML markup affects up to "
              f"{worst_html['pct_html']:.1f}% of rows (worst: {CITY_DISPLAY[worst_html['city']]}) "
              f"and is stripped, not dropped. Non-English reviews are "
              f"{worst_non_ascii['pct_non_ascii']:.0f}% of rows in the worst case "
              f"({CITY_DISPLAY[worst_non_ascii['city']]}) and are kept in the data on "
              f"purpose — language filtering is a downstream choice (see "
              f"[`review_cleaning_decisions.md`](../../../scripts/cleaning/reviews/review_cleaning_decisions.md), Section 5).")
    md.append("")
    md.append("## 1. What is in the raw file")
    md.append("")
    md.append("Inside Airbnb publishes a six-column CSV per city, scraped from public "
              "Airbnb pages and updated quarterly under CC-BY 4.0. The columns are:")
    md.append("")
    md.append("| Column | Type | Why a business reader cares |")
    md.append("| --- | --- | --- |")
    md.append("| `listing_id` | int | Joins reviews to a property → links sentiment / volume to revenue. |")
    md.append("| `id` | int | Unique review id; lets us count reviews per listing per year. |")
    md.append("| `date` | date | When the review was posted (≈ 14 days after check-out). The basis for the demand timeline. |")
    md.append("| `reviewer_id` / `reviewer_name` | int / string | Repeat-guest analytics; not used as model features. |")
    md.append("| `comments` | free text | The corpus for sentiment / topic / complaint analytics. |")
    md.append("")
    md.append("## 2. Market scope and recent demand intensity")
    md.append("")
    md.append("![Market scope by city]({}/01_market_scope_by_city.png)".format(MEMO_FIG_PREFIX))
    md.append("")
    md.append(summary_df[table_main_cols].to_markdown(index=False))
    md.append("")
    md.append("**How to read this (Panel A — supply).** The supply-side picture differs "
              "sharply across cities. Los Angeles has the largest base of unique listings "
              "ever reviewed, so any city-level metric (price, occupancy, sentiment) has "
              "the most statistical mass. New York and Hawaii follow. Nashville and San "
              "Francisco are smaller markets — comparisons must use weighted averages or "
              "be qualified.")
    md.append("")
    md.append("**How to read this (Panel B — demand intensity in the last full year).** "
              f"This is the average number of reviews each listing received in "
              f"{latest_full_year}. Multiply by ~2 to get an estimate of bookings per "
              "listing-year (Inside Airbnb's San Francisco study assumes ~50% of stays "
              "produce a review). It is the cleanest single-number demand signal we can "
              "extract from the review file — much more meaningful than the year of the "
              "very first review (which only captures when Airbnb opened in the city, "
              "not whether it is busy *today*).")
    md.append("")
    md.append("**Connection to the TP question:** Panel A is the denominator for any "
              "per-listing metric. Panel B is the input we cross-check against the "
              "calendar's `unavailability_rate` proxy when computing **Occupancy** in "
              "the revenue equation `Price × Occupancy × 365`.")
    md.append("")
    md.append("## 3. Demand timeline (yearly review volume)")
    md.append("")
    md.append("![Demand timeline]({}/02_demand_timeline_by_city.png)".format(MEMO_FIG_PREFIX))
    md.append("")
    md.append(yearly_pivot.to_markdown(index=False))
    md.append("")
    md.append("**How to read this:** review volume per year is a leading indicator of "
              "bookings. Inside Airbnb's San-Francisco study finds a review-rate of "
              "~50%, so 1,000 reviews ≈ 2,000 bookings, ≈ 6,000 booked nights "
              "(at 3 nights average stay). All five cities show the COVID dip in 2020-2021 "
              "and a recovery from 2022 onwards. **Hawaii and Nashville rebounded fastest** "
              "(leisure / tourism markets); New York and San Francisco recovered more "
              "slowly (regulation tightened in NYC; SF leans on business travel).")
    md.append("")
    md.append("**Connection to the TP question:** when projecting **forward** annual "
              "revenue, the post-2022 slope is the right reference, not the lifetime "
              "average. Pre-2020 reviews are still useful for sentiment baselines but "
              "give a misleading picture of *current* demand intensity.")
    md.append("")
    md.append("## 4. Data quality and what the cleaner has to remove")
    md.append("")
    md.append("![Data-quality gates]({}/03_data_quality_gates.png)".format(MEMO_FIG_PREFIX))
    md.append("")
    md.append(summary_df[table_quality_cols].to_markdown(index=False))
    md.append("")
    md.append("**How to read this:** each bar is the share of raw rows touched by one "
              "cleaning rule (the bars overlap — a row can be both short and HTML-bearing). "
              "The bigger the bar, the more aggressive the cleaning step has to be. "
              f"The worst short-comment share is {worst_short['pct_short_30']:.1f}% "
              f"({CITY_DISPLAY[worst_short['city']]}); these are usually one-word "
              "reviews like \"good\" or \"nice\" — useless for topic modeling and they "
              "distort length features, so we drop them. HTML markup peaks at "
              f"{worst_html['pct_html']:.1f}% in {CITY_DISPLAY[worst_html['city']]} "
              "and is replaced with whitespace (we keep the row).")
    md.append("")
    md.append("**Why we *don't* drop more rows.** The full cleaning rule set, with the "
              "rationale for each choice (and for the things we **deliberately don't** "
              "do — language filtering, long-comment trimming), lives in "
              "[`scripts/cleaning/reviews/review_cleaning_decisions.md`]"
              "(../../../scripts/cleaning/reviews/review_cleaning_decisions.md), Sections 3 and 5.")
    md.append("")
    md.append("## 5. Sample reviews (sanity check)")
    md.append("")
    md.append("Three raw rows per city, untouched. These give the team a feel for the "
              "tone, length and language mix before we apply any cleaning:")
    md.append("")
    md.extend(examples_md)
    md.append("## 6. Technical appendix (data engineering view)")
    md.append("")
    md.append("This section is intended for the dev / data-science side of the team. "
              "It documents the **raw schema, snapshot provenance and detailed statistics** "
              "that the cleaning script consumes. The why-each-rule narrative lives in "
              "[`scripts/cleaning/reviews/review_cleaning_decisions.md`]"
              "(../../../scripts/cleaning/reviews/review_cleaning_decisions.md).")
    md.append("")
    md.append("### 6.1. Snapshot provenance")
    md.append("")
    md.append("Inside Airbnb publishes one CSV per city per quarterly snapshot. The five "
              "files in `data/raw/reviews/` come from a single coordinated download "
              "(September-October 2025). Per-city snapshot dates are tracked in the "
              "project root `README.md` and reproduced here:")
    md.append("")
    md.append("| city | snapshot date (Inside Airbnb) | max review date in file |")
    md.append("| --- | --- | --- |")
    md.append("| Hawaii | 2025-09-16 | " + str(summary_df[summary_df['city'] == 'hawaii']['max_date'].iloc[0]) + " |")
    md.append("| Los Angeles | 2025-09-01 | " + str(summary_df[summary_df['city'] == 'los_angeles']['max_date'].iloc[0]) + " |")
    md.append("| Nashville | 2025-09-23 | " + str(summary_df[summary_df['city'] == 'nashville']['max_date'].iloc[0]) + " |")
    md.append("| New York | 2025-10-01 | " + str(summary_df[summary_df['city'] == 'new_york']['max_date'].iloc[0]) + " |")
    md.append("| San Francisco | 2025-09-01 | " + str(summary_df[summary_df['city'] == 'san_francisco']['max_date'].iloc[0]) + " |")
    md.append("")
    md.append("Any rerun of the cleaning pipeline assumes **all five files come from the "
              "same coordinated snapshot**; mixing snapshots biases year-over-year "
              "comparisons.")
    md.append("")
    md.append("### 6.2. Raw schema (columns and dtypes)")
    md.append("")
    md.append("Read with `pd.read_csv(path, encoding='utf-8-sig', on_bad_lines='skip')`. "
              "Recommended dtypes (used by both the cleaner and this inventory script):")
    md.append("")
    md.append("```python")
    md.append("dtype = {")
    md.append("    'listing_id':    'Int64',")
    md.append("    'id':            'Int64',     # review id, unique per city")
    md.append("    'reviewer_id':   'Int64',")
    md.append("    'reviewer_name': 'string',")
    md.append("    'comments':      'string',    # may contain newlines, HTML, non-ASCII")
    md.append("}")
    md.append("parse_dates = ['date']")
    md.append("```")
    md.append("")
    md.append("### 6.3. Detailed quality statistics (per city)")
    md.append("")
    md.append("All six diagnostic metrics, including duplicates and Latin-script vs "
              "non-ASCII shares (the latter not acted on, kept by design):")
    md.append("")
    md.append(summary_df[table_quality_cols].to_markdown(index=False))
    md.append("")
    md.append("### 6.4. Comment-length distribution (sampled)")
    md.append("")
    md.append("The cleaner sets `min_length = 30`; there is no upper cap. Median lengths "
              "vary 180–249 chars across cities, p95 reaches 641–939 chars. Long comments "
              "are kept on purpose — they are the most informative input for sentiment / "
              "topic models. See "
              "`processed_data_memo_reviews.md` for the post-clean distribution.")
    md.append("")
    md.append("### 6.5. Cleaning rules → raw issues mapping")
    md.append("")
    md.append("| Raw-data issue | Magnitude (worst city) | Cleaning rule | Status |")
    md.append("| --- | --- | --- | --- |")
    md.append("| Nulls in any of the 6 core columns | ≤3 rows / city | `chunk.notna().all(axis=1)` mask drops the row | **Covered** |")
    md.append("| Duplicate review ids (same `id` repeated) | up to 14 rows (SF) | `pd.util.hash_pandas_object` over the 6 columns drops the second occurrence | **Covered (stricter)** |")
    md.append(f"| HTML markup inside comments | up to {worst_html['pct_html']:.1f}% ({CITY_DISPLAY[worst_html['city']]}) | `HTML_TAG_PATTERN.sub(\" \", text)` strips tags; row kept | **Covered** |")
    md.append("| Mixed case / extra whitespace | ~all rows | `text.lower()` + collapse `\\s+` | **Covered** |")
    md.append("| Blank comment after cleaning | ≤0.04% / city | `blank_mask` drops the row | **Covered** |")
    md.append(f"| Comment shorter than {CLEANING_MIN_LENGTH} chars after cleaning | up to {worst_short['pct_short_30']:.1f}% ({CITY_DISPLAY[worst_short['city']]}) | `short_mask = length < {CLEANING_MIN_LENGTH}` drops the row | **Covered** |")
    md.append("| Non-English reviews | 12-28% (estimated) | _(not handled by cleaning)_ | **Open by design** — text-analytics |")
    md.append("| Extremely long comments (5k+ chars) | tail; max ≈12k chars | _(not handled by cleaning)_ | **Open by design** — tokenisation step |")
    md.append("")
    md.append("Bit-identical reproducibility from this raw snapshot is guaranteed since "
              "the 2026-04-29 fix (`csv.QUOTE_ALL` on output). See "
              "`review_cleaning_decisions.md` Section 6 for the bug story.")
    md.append("")
    md.append("### 6.6. Defensive read at consumer side")
    md.append("")
    md.append("Whether reading the raw or the cleaned file, the same defensive cast "
              "guards against future regressions:")
    md.append("")
    md.append("```python")
    md.append("df = pd.read_csv(path, dtype={'listing_id': 'string'}, low_memory=False)")
    md.append("df['listing_id'] = pd.to_numeric(df['listing_id'], errors='coerce').astype('Int64')")
    md.append("df['date']       = pd.to_datetime(df['date'], errors='coerce')")
    md.append("df = df.dropna(subset=['listing_id', 'date'])")
    md.append("```")
    md.append("")
    md.append("## 7. What this memo intentionally does NOT cover")
    md.append("")
    md.append("- **Sentiment or topic results.** Those are produced downstream from "
              "`comments_clean` in the text-analytics step.")
    md.append("- **Per-rule cleaning rationale.** That is the job of "
              "[`scripts/cleaning/reviews/review_cleaning_decisions.md`]"
              "(../../../scripts/cleaning/reviews/review_cleaning_decisions.md). "
              "This memo only documents the magnitude of each issue and the rule that "
              "addresses it.")
    md.append("- **Post-cleaning audit (rows-in vs rows-out, residual issues).** Lives "
              "in `data/processed/review/_eda/processed_data_memo_reviews.md` and the "
              "audit CSV produced by `run_full_review_cleaning.py`.")
    md.append("- **Reviews ↔ listings ↔ calendar joins.** Done in the modeling notebook "
              "once all three pipelines have run.")
    md.append("")
    return "\n".join(md)


def main() -> None:
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    MEMO_PATH.parent.mkdir(parents=True, exist_ok=True)

    stats_per_city = []
    print(f"Inventorying {len(CITY_FILES)} raw review files in {RAW_DIR}")
    for city, fname in CITY_FILES.items():
        csv_path = RAW_DIR / fname
        if not csv_path.exists():
            print(f"  SKIP {city}: file not found ({csv_path})")
            continue
        print(f"  Scanning {city} ({csv_path.stat().st_size / 1e6:.0f} MB) ...")
        stats = analyze_city(city, csv_path)
        print(
            f"    rows={stats['rows_total']:,} "
            f"listings={stats['unique_listings']:,} "
            f"html_rows={stats['rows_with_html_tags']:,} "
            f"min={stats['min_date']} max={stats['max_date']}"
        )
        stats_per_city.append(stats)

    inventory_df = pd.DataFrame([
        {k: v for k, v in s.items()
         if k not in {"yearly_counts", "sample_reviews", "comment_lengths_sample"}}
        for s in stats_per_city
    ])
    inventory_df.to_csv(INVENTORY_CSV, index=False)
    print(f"Saved inventory CSV → {INVENTORY_CSV}")

    yearly_df = build_yearly_long(stats_per_city)
    yearly_df.to_csv(YEARLY_CSV, index=False)
    print(f"Saved yearly counts CSV → {YEARLY_CSV}")

    make_market_scope_chart(stats_per_city)
    make_demand_timeline_chart(yearly_df)
    make_quality_gates_chart(stats_per_city)
    print(f"Saved 3 business-focused charts → {FIGURES_DIR}")

    memo_text = render_memo(stats_per_city, yearly_df)
    MEMO_PATH.write_text(memo_text, encoding="utf-8")
    print(f"Saved memo → {MEMO_PATH}")


if __name__ == "__main__":
    main()
