"""Calendar cleaning EDA — descriptive figures, one criterion per plot.

This script reads the **raw** Inside Airbnb calendar files
(``data/raw/calendars/calendar_<snake>.csv``) plus the per-city occupation
output (``data/processed/calendar/<snake>/occupation_<snake>_cleaned.csv``)
when available, and renders one focused figure per cleaning criterion.

The goal is to make the cleaning rules in
``scripts/cleaning/calendars/calendar_cleaning_decisions.md`` legible to a
business reader through the **data itself** (distributions, outliers, coverage)
rather than through a bullet list of rules.

Outputs (one chart per file, no multi-panel composites):

    01_calendar_price_outliers_by_city.png
        Boxplot of raw nightly ``price`` per city on a log scale, with the
        ``PRICE_HARD_CAP = $10,000`` line and counts of how many rows fall
        beyond the cap (rule §3.8 in the decisions memo).

    02_calendar_min_nights_outliers_by_city.png
        Boxplot of raw ``minimum_nights`` per city on a log scale, with the
        ``[1, 1125]`` clipping band and the share of rows that are clipped.

    03_calendar_max_nights_outliers_by_city.png
        Same as plot 02 for ``maximum_nights``.

    04_calendar_availability_distribution.png
        Histogram of per-listing ``availability_rate`` (computed during
        cleaning) by city, plus the dashed proxy ``occupancy = 1 - availability``.
        This shows the criterion behind ``occupancy_rate_proxy``.

    05_calendar_business_lens.png
        Per-city avg occupancy proxy, median nightly price, and median estimated
        annual revenue (the inputs of ``Price x Occupancy x 365``). One bar
        chart with three coloured groups.

To bound runtime / memory the raw calendars are read with chunksize and a
per-city sampling cap (default 500k rows per city — enough for stable
distributions on a log axis).

Run with the project venv from the repo root:
    .venv/bin/python scripts/eda/inventory_processed_calendar.py
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

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RANDOM_STATE = 42

FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "market_analysis" / "calendar"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

RAW_CALENDARS_DIR = PROJECT_ROOT / "data" / "raw" / "calendars"
PROCESSED_CALENDAR_DIR = PROJECT_ROOT / "data" / "processed" / "calendar"
CLEANED_LISTINGS_FILE = PROJECT_ROOT / "data" / "processed" / "listing_all_cleaned.csv"

CITY_LABEL_BY_SNAKE = {
    "hawaii": "Hawaii",
    "los_angeles": "Los Angeles",
    "nashville": "Nashville",
    "new_york": "New York",
    "san_francisco": "San Francisco",
}

AUDIT_CANDIDATES = [
    PROJECT_ROOT / "results" / "01_market_analysis" / "calendars" / "calendars_cleaning_audit.csv",
    PROJECT_ROOT / "data" / "processed" / "calendars" / "calendars_cleaning_audit.csv",
]

CITY_DISPLAY = {
    "hawaii": "Hawaii",
    "los_angeles": "Los Angeles",
    "nashville": "Nashville",
    "new_york": "New York",
    "san_francisco": "San Francisco",
}

# Hard caps as defined in scripts/cleaning/calendars/run_full_calendar_cleaning.py.
PRICE_HARD_CAP = 10_000.0
NIGHTS_HARD_CAP = 1125

CHUNK_SIZE = 200_000
SAMPLE_CAP_PER_CITY = 500_000  # rows
PRICE_CLEAN_PATTERN = re.compile(r"[^0-9.\-]")

SOURCE_FOOTER = (
    "Source: data/raw/calendars/calendar_<city>.csv (Inside Airbnb 2024-25 snapshots).\n"
    "Cleaning rules: scripts/cleaning/calendars/calendar_cleaning_decisions.md."
)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #

def _normalize_price_series(series: pd.Series) -> pd.Series:
    """Strip $, commas and whitespace, return numeric series with NaN on errors."""
    cleaned = (
        series.astype("string").str.strip()
        .str.replace(PRICE_CLEAN_PATTERN, "", regex=True)
        .replace({"": pd.NA})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _stream_raw_columns(csv_path: Path, columns: list[str], cap: int) -> pd.DataFrame:
    """Read up to ``cap`` parsed rows from ``csv_path`` for the given columns.

    Streaming in chunks so we never materialize the full file (raw calendars
    range from ~100MB to ~620MB on disk).
    """
    out: list[pd.DataFrame] = []
    rows = 0
    for chunk in pd.read_csv(csv_path, usecols=columns, chunksize=CHUNK_SIZE, low_memory=False):
        out.append(chunk)
        rows += len(chunk)
        if rows >= cap:
            break
    if not out:
        return pd.DataFrame(columns=columns)
    df = pd.concat(out, ignore_index=True)
    if len(df) > cap:
        df = df.sample(cap, random_state=RANDOM_STATE).reset_index(drop=True)
    return df


def _load_raw_distributions() -> dict[str, pd.DataFrame]:
    """Return per-city sampled DataFrames with ``minimum_nights`` and ``maximum_nights``.

    Note: the raw calendar's ``price`` column is empty in the recent Inside
    Airbnb dumps, so price outliers are sourced from the listings master
    (``data/processed/listing_all_cleaned.csv``) via ``_load_listing_prices``.
    """
    frames: dict[str, pd.DataFrame] = {}
    for snake in CITY_DISPLAY:
        csv_path = RAW_CALENDARS_DIR / f"calendar_{snake}.csv"
        if not csv_path.exists():
            print(f"WARN: missing raw calendar for {snake}: {csv_path}")
            continue
        df = _stream_raw_columns(csv_path, ["minimum_nights", "maximum_nights"], SAMPLE_CAP_PER_CITY)
        df["minimum_nights"] = pd.to_numeric(df["minimum_nights"], errors="coerce")
        df["maximum_nights"] = pd.to_numeric(df["maximum_nights"], errors="coerce")
        frames[snake] = df
        print(f"  loaded {snake}: {len(df):,} sampled rows ({csv_path.stat().st_size / 1e6:.0f} MB on disk)")
    return frames


RAW_LISTING_DIR = PROJECT_ROOT / "data" / "raw" / "listing"


def _load_listing_prices() -> tuple[dict[str, pd.Series], str]:
    """Return per-city listing-price series.

    Calendar price columns are empty in the raw 2024-25 snapshots, so the
    price hard cap (rule §3.8 in the decisions memo) is enforced inside
    ``load_listing_prices()`` of run_full_calendar_cleaning.py against the
    listing master. We try the cleaned master first; if it doesn't exist
    yet (pipeline not re-run), we fall back to the raw per-city listings.
    """
    out: dict[str, pd.Series] = {}

    if CLEANED_LISTINGS_FILE.exists():
        df = pd.read_csv(
            CLEANED_LISTINGS_FILE,
            usecols=["price", "City"],
            encoding="utf-8-sig",
            low_memory=False,
        )
        df["price"] = _normalize_price_series(df["price"])
        for snake, label in CITY_LABEL_BY_SNAKE.items():
            sub = df.loc[df["City"].eq(label), "price"].dropna()
            out[snake] = sub
        return out, str(CLEANED_LISTINGS_FILE.relative_to(PROJECT_ROOT))

    if RAW_LISTING_DIR.exists():
        for snake in CITY_LABEL_BY_SNAKE:
            csv_path = RAW_LISTING_DIR / f"listings_{snake}.csv"
            if not csv_path.exists():
                print(f"WARN: missing raw listings for {snake}: {csv_path}")
                continue
            df = pd.read_csv(csv_path, usecols=["price"], low_memory=False)
            out[snake] = _normalize_price_series(df["price"]).dropna()
        return out, "data/raw/listing/listings_<city>.csv (cleaned master not built yet)"

    print("WARN: neither listing master nor raw listings found; plot 01 will be empty.")
    return out, "(no listing source found)"


def _load_audit() -> pd.DataFrame:
    for path in AUDIT_CANDIDATES:
        if path.exists():
            audit = pd.read_csv(path, encoding="utf-8-sig")
            audit["audit_source"] = str(path.relative_to(PROJECT_ROOT))
            return audit
    raise FileNotFoundError(
        "No calendars_cleaning_audit.csv found. Looked in: "
        + ", ".join(str(p.relative_to(PROJECT_ROOT)) for p in AUDIT_CANDIDATES)
    )


def _load_availability() -> pd.DataFrame | None:
    """Concat per-city occupation outputs into one DataFrame.

    Returns ``None`` when occupation outputs are not present yet (e.g. the
    pipeline hasn't been re-run after the latest cleanup).
    """
    rows: list[pd.DataFrame] = []
    for snake in CITY_DISPLAY:
        path = PROCESSED_CALENDAR_DIR / snake / f"occupation_{snake}_cleaned.csv"
        if not path.exists():
            continue
        rows.append(pd.read_csv(path, usecols=["listing_id", "city", "availability_rate"], encoding="utf-8-sig"))
    if not rows:
        return None
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- #
# Plotting helpers
# --------------------------------------------------------------------------- #

CITY_ORDER = list(CITY_DISPLAY.keys())
CITY_PALETTE = {
    "hawaii": "#1F4E79",
    "los_angeles": "#5B9BD5",
    "nashville": "#7FB069",
    "new_york": "#D88C2D",
    "san_francisco": "#C77B7B",
}


def _style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)


def _city_box_data(frames: dict[str, pd.DataFrame], col: str, drop_nonpositive: bool) -> tuple[list[np.ndarray], list[str]]:
    data: list[np.ndarray] = []
    labels: list[str] = []
    for snake in CITY_ORDER:
        if snake not in frames:
            continue
        s = frames[snake][col].dropna().to_numpy()
        if drop_nonpositive:
            s = s[s > 0]
        data.append(s)
        labels.append(CITY_DISPLAY[snake])
    return data, labels


def _format_count_share(count: int, total: int) -> str:
    if total <= 0:
        return f"{count:,}"
    pct = count / total * 100
    if pct < 0.001:
        return f"{count:,} (<0.001%)"
    return f"{count:,} ({pct:.3f}%)"


# --------------------------------------------------------------------------- #
# Plot 01 — Price outliers
# --------------------------------------------------------------------------- #

def _set_title_and_subtitle(fig: plt.Figure, ax: plt.Axes, title: str, subtitle: str) -> None:
    """Place a bold title and a softer subtitle above the axes without overlap."""
    fig.suptitle(title, fontsize=13, fontweight="bold", x=0.05, y=1.02, ha="left")
    ax.set_title(subtitle, fontsize=9.5, color="#4A5468", loc="left", pad=12)


def render_price_outliers(price_by_city: dict[str, pd.Series], output_path: Path) -> None:
    data: list[np.ndarray] = []
    labels: list[str] = []
    snake_used: list[str] = []
    for snake in CITY_ORDER:
        s = price_by_city.get(snake)
        if s is None or s.empty:
            continue
        arr = s.to_numpy()
        arr = arr[arr > 0]
        if arr.size == 0:
            continue
        data.append(arr)
        labels.append(CITY_DISPLAY[snake])
        snake_used.append(snake)

    fig, ax = plt.subplots(figsize=(11, 6.2))
    if not data:
        ax.set_axis_off()
        ax.text(
            0.5, 0.5,
            "Listing prices unavailable.\n\n"
            "Run scripts/cleaning/listing/run_full_listing_cleaning.py first\n"
            "to produce data/processed/listing_all_cleaned.csv.",
            ha="center", va="center", fontsize=11,
            bbox=dict(facecolor="#F2F5FA", edgecolor="#C9D2E2", boxstyle="round,pad=0.6"),
        )
        _set_title_and_subtitle(
            fig, ax,
            "Price outliers per city — what gets nulled by the $10,000 hard cap",
            "Source for this plot: data/processed/listing_all_cleaned.csv "
            "(raw calendar.price is empty in the 2024-25 snapshots).",
        )
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return

    bp = ax.boxplot(
        data, tick_labels=labels, vert=True, showfliers=True,
        patch_artist=True, widths=0.55,
        flierprops=dict(marker="o", markersize=2.5, markerfacecolor="#1F2A44", markeredgecolor="none", alpha=0.35),
        medianprops=dict(color="white", linewidth=1.6),
        whiskerprops=dict(color="#1F2A44"),
        capprops=dict(color="#1F2A44"),
    )
    for patch, snake in zip(bp["boxes"], snake_used):
        patch.set_facecolor(CITY_PALETTE[snake])
        patch.set_alpha(0.85)

    ax.set_yscale("log")
    ax.axhline(PRICE_HARD_CAP, color="#B1361F", linestyle="--", linewidth=1.6, label=f"Hard cap = ${PRICE_HARD_CAP:,.0f}")

    annotation_lines = ["Listings beyond $10K hard cap:"]
    for snake in snake_used:
        prices = price_by_city[snake]
        beyond = int((prices > PRICE_HARD_CAP).sum())
        annotation_lines.append(f"  {CITY_DISPLAY[snake]:<14}{_format_count_share(beyond, len(prices))}")
    ax.text(
        1.005, 0.5, "\n".join(annotation_lines),
        transform=ax.transAxes, fontsize=8.5, family="monospace", va="center", ha="left",
        bbox=dict(facecolor="#F2F5FA", edgecolor="#C9D2E2", boxstyle="round,pad=0.4"),
    )

    ax.set_ylabel("Nightly price (USD, log scale)")
    ax.set_xlabel("")
    _set_title_and_subtitle(
        fig, ax,
        "Price outliers per city — what gets nulled by the $10,000 hard cap",
        "Listing-master price (calendar.price is empty in the 2024-25 dump). "
        "Decisions memo §3.8: price > $10,000 → NaN.",
    )
    ax.legend(loc="upper right", frameon=False)
    _style_ax(ax)

    fig.text(0.5, -0.04, SOURCE_FOOTER, ha="center", fontsize=8, color="#4A5468")
    fig.subplots_adjust(right=0.78)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Plot 02/03 — Nights outliers
# --------------------------------------------------------------------------- #

def render_nights_outliers(
    frames: dict[str, pd.DataFrame],
    column: str,
    title: str,
    subtitle: str,
    output_path: Path,
) -> None:
    data, labels = _city_box_data(frames, column, drop_nonpositive=True)
    if not data:
        print(f"WARN: no {column} data available; skipping plot for {column}")
        return

    fig, ax = plt.subplots(figsize=(11, 6.2))
    bp = ax.boxplot(
        data, tick_labels=labels, vert=True, showfliers=True,
        patch_artist=True, widths=0.55,
        flierprops=dict(marker="o", markersize=2.5, markerfacecolor="#1F2A44", markeredgecolor="none", alpha=0.35),
        medianprops=dict(color="white", linewidth=1.6),
        whiskerprops=dict(color="#1F2A44"),
        capprops=dict(color="#1F2A44"),
    )
    for patch, snake in zip(bp["boxes"], [c for c in CITY_ORDER if c in frames]):
        patch.set_facecolor(CITY_PALETTE[snake])
        patch.set_alpha(0.85)

    ax.set_yscale("log")
    ax.axhline(1, color="#4A5468", linestyle=":", linewidth=1.2, label="Lower clip = 1")
    ax.axhline(NIGHTS_HARD_CAP, color="#B1361F", linestyle="--", linewidth=1.6, label=f"Upper clip = {NIGHTS_HARD_CAP:,}")

    annotation_lines = ["Rows clipped (sampled):"]
    for snake in CITY_ORDER:
        if snake not in frames:
            continue
        s = frames[snake][column].dropna()
        outside = int(((s < 1) | (s > NIGHTS_HARD_CAP)).sum())
        annotation_lines.append(f"  {CITY_DISPLAY[snake]:<14}{_format_count_share(outside, len(s))}")
    ax.text(
        1.005, 0.5, "\n".join(annotation_lines),
        transform=ax.transAxes, fontsize=8.5, family="monospace", va="center", ha="left",
        bbox=dict(facecolor="#F2F5FA", edgecolor="#C9D2E2", boxstyle="round,pad=0.4"),
    )

    ax.set_ylabel(f"{column} (log scale)")
    ax.set_xlabel("")
    _set_title_and_subtitle(fig, ax, title, subtitle)
    ax.legend(loc="upper right", frameon=False)
    _style_ax(ax)

    fig.text(0.5, -0.04, SOURCE_FOOTER, ha="center", fontsize=8, color="#4A5468")
    fig.subplots_adjust(right=0.78)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Plot 04 — Availability distribution (criterion behind occupancy proxy)
# --------------------------------------------------------------------------- #

def render_availability_distribution(occupation: pd.DataFrame | None, output_path: Path) -> None:
    if occupation is None or occupation.empty:
        print("WARN: no occupation outputs found; rendering placeholder for plot 04")
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.set_axis_off()
        ax.text(
            0.5, 0.5,
            "Per-listing availability distribution unavailable.\n\n"
            "Run the cleaning pipeline first to produce\n"
            "data/processed/calendar/<city>/occupation_<city>_cleaned.csv:\n\n"
            "    python scripts/cleaning/run_cleaning_pipeline.py",
            ha="center", va="center", fontsize=11,
            bbox=dict(facecolor="#F2F5FA", edgecolor="#C9D2E2", boxstyle="round,pad=0.6"),
        )
        _set_title_and_subtitle(
            fig, ax,
            "Availability distribution per listing — basis for the occupancy proxy",
            "Pending: re-run the cleaning pipeline to materialise occupation_<city>_cleaned.csv.",
        )
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return

    fig, ax = plt.subplots(figsize=(11, 6.2))
    bins = np.linspace(0, 1, 41)
    for snake in CITY_ORDER:
        sub = occupation.loc[occupation["city"] == snake, "availability_rate"].dropna()
        if sub.empty:
            continue
        ax.hist(
            sub, bins=bins, density=True, histtype="step",
            linewidth=1.8, label=CITY_DISPLAY[snake], color=CITY_PALETTE[snake],
        )

    ax.axvspan(0, 0.2, color="#D88C2D", alpha=0.08, label="High occupancy proxy (avail < 20%)")
    ax.set_xlabel("availability_rate per listing  (= n_days_available / n_days)")
    ax.set_ylabel("Density of listings")
    ax.set_xlim(0, 1)
    _set_title_and_subtitle(
        fig, ax,
        "Availability distribution per listing — the basis for the occupancy proxy",
        "occupancy_rate_proxy = 1 − availability_rate. Covers EVERY calendar listing (incl. hosts blocking all year, esp. NYC).\n"
        "Q1–Q4 use master_data.csv (only listings with a valid price), which yields ~25 pp lower occupancy in NYC.",
    )
    ax.legend(frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.20))
    _style_ax(ax)

    fig.subplots_adjust(bottom=0.22)
    fig.text(0.5, -0.16, SOURCE_FOOTER, ha="center", fontsize=8, color="#4A5468")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Plot 05 — Business lens (revenue equation inputs)
# --------------------------------------------------------------------------- #

def render_business_lens(audit: pd.DataFrame, output_path: Path) -> None:
    cities = [c for c in CITY_ORDER if c in audit["city"].tolist()]
    audit = audit.set_index("city").loc[cities].reset_index()

    fig, ax = plt.subplots(figsize=(11, 6.2))
    x = np.arange(len(cities))
    width = 0.27

    occupancy = audit["avg_occupancy_proxy"].astype(float).fillna(0) * 100
    price = audit["median_listing_price"].astype(float).fillna(0)
    revenue = audit["median_est_annual_revenue_proxy"].astype(float).fillna(0) / 1000

    occupancy_norm = occupancy / max(occupancy.max(), 1) * 100
    price_norm = price / max(price.max(), 1) * 100
    revenue_norm = revenue / max(revenue.max(), 1) * 100

    bars_occ = ax.bar(x - width, occupancy_norm, width, label="Occupancy proxy", color="#1F4E79")
    bars_price = ax.bar(x, price_norm, width, label="Median nightly price", color="#7FB069")
    bars_rev = ax.bar(x + width, revenue_norm, width, label="Median annual revenue proxy", color="#D88C2D")

    for bars, raw, fmt in (
        (bars_occ, occupancy, lambda v: f"{v:.0f}%"),
        (bars_price, price, lambda v: f"${v:,.0f}"),
        (bars_rev, revenue, lambda v: f"${v:,.1f}K"),
    ):
        for bar, value in zip(bars, raw):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                fmt(value), ha="center", va="bottom", fontsize=9, color="#1F2A44",
            )

    ax.set_xticks(x)
    ax.set_xticklabels([CITY_DISPLAY[c] for c in cities], rotation=15, ha="right")
    ax.set_ylabel("Indexed scale (each metric normalised to its own max = 100)")
    ax.set_ylim(0, 120)
    _set_title_and_subtitle(
        fig, ax,
        "Inputs of the revenue equation — Price x Occupancy x 365",
        "Each group of three bars is one city. Numbers above bars show the raw value; bar height is normalised.\n"
        "Caveat: audit-level occupancy includes 'blocked-all-year' listings (esp. NYC); Q1–Q4 use master_data and report lower values.",
    )
    ax.legend(frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.20))
    _style_ax(ax)

    fig.subplots_adjust(bottom=0.22)
    fig.text(0.5, -0.16, SOURCE_FOOTER, ha="center", fontsize=8, color="#4A5468")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def _cleanup_legacy_outputs() -> None:
    legacy = [
        FIGURES_DIR / "01_calendar_pipeline_funnel.png",
        FIGURES_DIR / "02_calendar_business_lens.png",
    ]
    for path in legacy:
        if path.exists():
            path.unlink()
            print(f"removed legacy figure: {path.relative_to(PROJECT_ROOT)}")


def main() -> None:
    _cleanup_legacy_outputs()

    print("Loading raw calendar samples (this can take a minute on large cities)...")
    frames = _load_raw_distributions()

    print("Loading listing-master prices for the price-cap plot...")
    price_by_city, price_source = _load_listing_prices()
    print(f"  source: {price_source}")
    if price_by_city:
        for snake, series in price_by_city.items():
            print(f"  {snake}: {len(series):,} listings with parsed price")

    audit = _load_audit()
    print(f"Loaded calendar audit: {audit['audit_source'].iloc[0]}")

    occupation = _load_availability()
    if occupation is not None:
        print(f"Loaded occupation rates for {occupation['city'].nunique()} cities ({len(occupation):,} listings)")
    else:
        print("Occupation outputs not found — plot 04 will render a placeholder.")

    plot_paths = [
        ("01_calendar_price_outliers_by_city.png",
         lambda p: render_price_outliers(price_by_city, p)),
        ("02_calendar_min_nights_outliers_by_city.png",
         lambda p: render_nights_outliers(
             frames, "minimum_nights",
             "Minimum-nights outliers per city — what gets clipped to [1, 1125]",
             "Boxplot of raw minimum_nights (random sample of up to 500K rows per city). "
             "Decisions memo §3.8: clip to [1, 1125].",
             p,
         )),
        ("03_calendar_max_nights_outliers_by_city.png",
         lambda p: render_nights_outliers(
             frames, "maximum_nights",
             "Maximum-nights outliers per city — what gets clipped to [1, 1125]",
             "Boxplot of raw maximum_nights (random sample of up to 500K rows per city). "
             "Decisions memo §3.8: clip to [1, 1125].",
             p,
         )),
        ("04_calendar_availability_distribution.png",
         lambda p: render_availability_distribution(occupation, p)),
        ("05_calendar_business_lens.png",
         lambda p: render_business_lens(audit, p)),
    ]

    for filename, renderer in plot_paths:
        out_path = FIGURES_DIR / filename
        renderer(out_path)
        print(f"Wrote {out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
