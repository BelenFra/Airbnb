"""Q4 — How does seasonality affect revenue in each city? Is demand stable
year-round or concentrated in peak months?

Inputs
------
- ``data/processed/calendar_all_cleaned.csv`` (row-level, ~3 GB)

Outputs
-------
- ``results/01_market_analysis/q4_seasonality/monthly_metrics.csv``
- ``results/01_market_analysis/q4_seasonality/per_city_seasonality.csv``
- ``results/01_market_analysis/q4_seasonality/q4_summary.md``
- ``reports/figures/market_analysis/q4_seasonality/01_q4_monthly_demand.png``
- ``reports/figures/market_analysis/q4_seasonality/02_q4_monthly_revenue.png``
- ``reports/figures/market_analysis/q4_seasonality/03_q4_seasonality_strength.png``

Method
------
Per (city, calendar month) we compute:

- ``demand_proxy``        = 1 − mean(available)           (occupancy proxy)
- ``median_listing_price``= **constant per city**, taken from the cleaned
                            ``master_data.csv``. The Inside Airbnb calendar
                            file leaves ``price`` and ``adjusted_price`` empty
                            (this is documented in the calendar cleaning memo),
                            so we cannot estimate per-month price seasonality
                            from this snapshot — only demand seasonality.
- ``revenue_per_listing`` = ``demand_proxy × median_listing_price × days_in_month``

Then per city we summarise seasonality strength with:

- **CV** (coefficient of variation) = std / mean across months — higher = more
  seasonal.
- **Peak / off-peak ratio** = max month value / min month value.
- **Peak month** and **off-peak month** for both demand and revenue.

To handle the 3 GB row-level file we read it in chunks (``CHUNK_ROWS``) and
aggregate incrementally. ``load_data`` does not support chunked reads, so this
is one of the toolkit gaps; everything else still goes through the toolkit.

Toolkit usage
-------------
- ``get_summary_statistics`` for the headline numbers on the per-city pivot
- All plotting is grouped-line / multi-axis which is not in the toolkit, so
  plain matplotlib is used (toolkit gap).

Run
---
    .venv/bin/python scripts/market_analysis/q4_seasonality.py
"""

from __future__ import annotations

import calendar
import os
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

import mba706_toolkit as mba

RANDOM_STATE = 42

CALENDAR_FILE = PROJECT_ROOT / "data" / "processed" / "calendar_all_cleaned.csv"
MASTER_FILE = PROJECT_ROOT / "data" / "processed" / "master_data.csv"
RESULTS_DIR = PROJECT_ROOT / "results" / "01_market_analysis" / "q4_seasonality"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "market_analysis" / "q4_seasonality"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_ROWS = 1_500_000

# The Inside Airbnb snapshot was scraped in Sept 2025, so the first and last
# month of every per-city calendar are PARTIAL (incomplete day count). They
# bias seasonality if kept, so we drop them and only keep months whose row count
# is at least PARTIAL_THRESHOLD * max_month_rows (per city).
PARTIAL_THRESHOLD = 0.85

CITY_LABEL_BY_SNAKE = {
    "hawaii": "Hawaii",
    "los_angeles": "Los Angeles",
    "nashville": "Nashville",
    "new_york": "New York",
    "san_francisco": "San Francisco",
}
CITY_ORDER = ["Hawaii", "Los Angeles", "Nashville", "New York", "San Francisco"]
CITY_COLORS = {
    "Hawaii":         "#1f77b4",
    "Los Angeles":    "#ff7f0e",
    "Nashville":      "#2ca02c",
    "New York":       "#d62728",
    "San Francisco":  "#9467bd",
}

USECOLS = ["city", "date", "available"]


# ---------------------------------------------------------------------------
# 1. Per-city listing price (constant) from master_data
# ---------------------------------------------------------------------------

def median_price_per_city() -> pd.Series:
    print(f"Loading {MASTER_FILE.relative_to(PROJECT_ROOT)} for per-city listing prices ...")
    info = mba.load_data(str(MASTER_FILE), dataset_name="master")
    if info["status"] != "success":
        raise RuntimeError(f"toolkit load_data failed: {info}")
    df = mba._data_store["master"]
    df = df.copy()
    df["price_num"] = pd.to_numeric(df["price"], errors="coerce")
    series = df.dropna(subset=["price_num"]).groupby("City")["price_num"].median()
    print("  median listing price per city:")
    for city, val in series.items():
        print(f"    {city:<15} = ${val:,.0f}")
    return series


# ---------------------------------------------------------------------------
# 2. Chunked calendar aggregation (toolkit gap: load_data has no chunksize)
# ---------------------------------------------------------------------------

def aggregate_calendar(city_price: pd.Series) -> pd.DataFrame:
    print(f"Streaming {CALENDAR_FILE.relative_to(PROJECT_ROOT)} in chunks of {CHUNK_ROWS:,} rows ...")
    accum = []
    rows_seen = 0
    chunk_id = 0
    for chunk in pd.read_csv(
        CALENDAR_FILE,
        usecols=USECOLS,
        dtype={"city": "string", "available": "bool"},
        parse_dates=["date"],
        chunksize=CHUNK_ROWS,
        encoding="utf-8-sig",
    ):
        chunk_id += 1
        rows_seen += len(chunk)
        chunk["year_month"] = chunk["date"].dt.to_period("M")
        grp = chunk.groupby(["city", "year_month"], observed=True)
        agg = grp.agg(
            rows=("available", "size"),
            available_count=("available", "sum"),
        )
        accum.append(agg)
        if chunk_id % 5 == 0:
            print(f"  processed {rows_seen:,} rows so far ...")
    print(f"  done. total rows seen = {rows_seen:,}")

    combined = pd.concat(accum)
    final = combined.groupby(level=[0, 1]).sum()
    final = final.reset_index()
    final["year_month"] = final["year_month"].astype(str)
    final["available_share"] = final["available_count"] / final["rows"]
    final["demand_proxy"] = 1.0 - final["available_share"]

    final["year"] = final["year_month"].str.slice(0, 4).astype(int)
    final["month"] = final["year_month"].str.slice(5, 7).astype(int)
    final["days_in_month"] = final.apply(
        lambda r: calendar.monthrange(int(r["year"]), int(r["month"]))[1], axis=1
    )
    final["City"] = final["city"].map(CITY_LABEL_BY_SNAKE).fillna(final["city"])
    final["median_listing_price"] = final["City"].map(city_price)
    final["revenue_per_listing"] = (
        final["demand_proxy"] * final["median_listing_price"] * final["days_in_month"]
    )

    final = final[[
        "City", "year_month", "year", "month", "days_in_month",
        "rows", "available_count",
        "available_share", "demand_proxy",
        "median_listing_price", "revenue_per_listing",
    ]]
    final["is_complete_month"] = True
    max_rows_per_city = final.groupby("City")["rows"].transform("max")
    final.loc[final["rows"] < max_rows_per_city * PARTIAL_THRESHOLD,
              "is_complete_month"] = False
    dropped = final.loc[~final["is_complete_month"], ["City", "year_month", "rows"]]
    if not dropped.empty:
        print(f"\nDropping {len(dropped)} partial months "
              f"(below {PARTIAL_THRESHOLD:.0%} of the max month size per city):")
        for _, r in dropped.iterrows():
            print(f"  {r['City']:<15} {r['year_month']}  rows={int(r['rows']):,}")
    return final


# ---------------------------------------------------------------------------
# 2. Per-city seasonality summary
# ---------------------------------------------------------------------------

def per_city_seasonality(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    monthly = monthly[monthly["is_complete_month"]].copy()
    for city, sub in monthly.groupby("City"):
        sub = sub.sort_values("year_month")
        demand = sub["demand_proxy"].dropna()
        revenue = sub["revenue_per_listing"].dropna()
        if demand.empty or revenue.empty:
            continue

        peak_demand = sub.loc[demand.idxmax()]
        low_demand = sub.loc[demand.idxmin()]
        peak_rev = sub.loc[revenue.idxmax()]
        low_rev = sub.loc[revenue.idxmin()]

        rows.append({
            "City": city,
            "n_months": len(sub),
            "demand_mean": round(demand.mean(), 4),
            "demand_std": round(demand.std(), 4),
            "demand_cv": round(demand.std() / demand.mean(), 4) if demand.mean() else np.nan,
            "demand_peak_month": peak_demand["year_month"],
            "demand_peak_value": round(peak_demand["demand_proxy"], 4),
            "demand_low_month": low_demand["year_month"],
            "demand_low_value": round(low_demand["demand_proxy"], 4),
            "demand_peak_to_low": (
                round(peak_demand["demand_proxy"] / low_demand["demand_proxy"], 2)
                if low_demand["demand_proxy"] else np.nan
            ),
            "revenue_mean": round(revenue.mean(), 2),
            "revenue_std": round(revenue.std(), 2),
            "revenue_cv": round(revenue.std() / revenue.mean(), 4) if revenue.mean() else np.nan,
            "revenue_peak_month": peak_rev["year_month"],
            "revenue_peak_value": round(peak_rev["revenue_per_listing"], 2),
            "revenue_low_month": low_rev["year_month"],
            "revenue_low_value": round(low_rev["revenue_per_listing"], 2),
            "revenue_peak_to_low": (
                round(peak_rev["revenue_per_listing"] / low_rev["revenue_per_listing"], 2)
                if low_rev["revenue_per_listing"] else np.nan
            ),
        })
    res = pd.DataFrame(rows).set_index("City")
    res = res.reindex([c for c in CITY_ORDER if c in res.index])
    return res


# ---------------------------------------------------------------------------
# 3. Plots (toolkit gap: grouped-line + multi-axis)
# ---------------------------------------------------------------------------

def plot_monthly_demand(monthly: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "01_q4_monthly_demand.png"
    fig, ax = plt.subplots(figsize=(13, 6))
    plot_data = monthly[monthly["is_complete_month"]].copy()
    pivot = plot_data.pivot_table(index="year_month", columns="City",
                                  values="demand_proxy", aggfunc="mean")
    pivot = pivot.sort_index()
    # Drop months where less than 4 of 5 cities have a complete month —
    # they would only show 1-2 dots and add visual noise.
    pivot = pivot.loc[pivot.notna().sum(axis=1) >= 4]
    for city in [c for c in CITY_ORDER if c in pivot.columns]:
        ax.plot(pivot.index, pivot[city], marker="o", markersize=4,
                color=CITY_COLORS[city], label=city, linewidth=1.6)
    ax.set_ylabel("Demand proxy (1 − available share)")
    ax.set_title("Source: data/processed/calendar_all_cleaned.csv (per-day occupancy aggregated by month)",
                 fontsize=10, color="dimgray", pad=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(0, max(0.7, pivot.max().max() * 1.08))
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", ncol=3, fontsize=9)

    ticks = list(pivot.index)
    step = max(1, len(ticks) // 12)
    ax.set_xticks(ticks[::step])
    ax.set_xticklabels(ticks[::step], rotation=35, ha="right")

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q4 — Monthly demand proxy per city",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_monthly_revenue(monthly: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "02_q4_monthly_revenue.png"
    fig, ax = plt.subplots(figsize=(13, 6))
    plot_data = monthly[monthly["is_complete_month"]].copy()
    pivot = plot_data.pivot_table(index="year_month", columns="City",
                                  values="revenue_per_listing", aggfunc="mean")
    pivot = pivot.sort_index()
    pivot = pivot.loc[pivot.notna().sum(axis=1) >= 4]
    for city in [c for c in CITY_ORDER if c in pivot.columns]:
        ax.plot(pivot.index, pivot[city], marker="o", markersize=4,
                color=CITY_COLORS[city], label=city, linewidth=1.6)
    ax.set_ylabel("Estimated revenue per listing (USD per month)")
    ax.set_title("revenue = demand_proxy × median_listing_price (per city) × days_in_month",
                 fontsize=10, color="dimgray", pad=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", ncol=3, fontsize=9)

    ticks = list(pivot.index)
    step = max(1, len(ticks) // 12)
    ax.set_xticks(ticks[::step])
    ax.set_xticklabels(ticks[::step], rotation=35, ha="right")

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q4 — Monthly revenue per listing per city",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_seasonality_strength(per_city: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "03_q4_seasonality_strength.png"
    fig, ax1 = plt.subplots(figsize=(11, 6))
    cities = list(per_city.index)
    x = np.arange(len(cities))
    width = 0.36
    ax2 = ax1.twinx()

    bars1 = ax1.bar(x - width / 2, per_city["demand_cv"],
                    width, color="#3b6fb6", edgecolor="black", alpha=0.85,
                    label="Demand CV (left)")
    bars2 = ax2.bar(x + width / 2, per_city["revenue_cv"],
                    width, color="#e07b39", edgecolor="black", alpha=0.85,
                    label="Revenue CV (right)")
    for bar, v in zip(bars1, per_city["demand_cv"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, v,
                 f" {v:.2f}", ha="center", va="bottom", fontsize=8)
    for bar, v in zip(bars2, per_city["revenue_cv"]):
        ax2.text(bar.get_x() + bar.get_width() / 2, v,
                 f" {v:.2f}", ha="center", va="bottom", fontsize=8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(cities, rotation=15, ha="right")
    ax1.set_ylabel("Coefficient of variation (demand)", color="#3b6fb6")
    ax2.set_ylabel("Coefficient of variation (revenue)", color="#e07b39")
    ax1.set_title("Higher CV = more seasonal (revenue/demand swing more across months)",
                  fontsize=10, color="dimgray", pad=8)
    ax1.grid(axis="y", linestyle="--", alpha=0.35)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q4 — Seasonality strength per city",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 4. Markdown
# ---------------------------------------------------------------------------

def write_markdown(monthly: pd.DataFrame, per_city: pd.DataFrame,
                   monthly_csv: Path, summary_csv: Path,
                   plot_paths: list[Path]) -> Path:
    out = RESULTS_DIR / "q4_summary.md"
    rel_monthly = monthly_csv.relative_to(PROJECT_ROOT)
    rel_summary = summary_csv.relative_to(PROJECT_ROOT)

    most_seasonal = per_city["revenue_cv"].idxmax()
    least_seasonal = per_city["revenue_cv"].idxmin()

    pc_md = per_city.copy()
    pc_md["demand_mean"] = pc_md["demand_mean"].apply(lambda v: f"{v:.1%}")
    pc_md["demand_std"] = pc_md["demand_std"].apply(lambda v: f"{v:.3f}")
    pc_md["demand_peak_value"] = pc_md["demand_peak_value"].apply(lambda v: f"{v:.1%}")
    pc_md["demand_low_value"] = pc_md["demand_low_value"].apply(lambda v: f"{v:.1%}")
    pc_md["revenue_mean"] = pc_md["revenue_mean"].apply(lambda v: f"${v:,.0f}")
    pc_md["revenue_std"] = pc_md["revenue_std"].apply(lambda v: f"${v:,.0f}")
    pc_md["revenue_peak_value"] = pc_md["revenue_peak_value"].apply(lambda v: f"${v:,.0f}")
    pc_md["revenue_low_value"] = pc_md["revenue_low_value"].apply(lambda v: f"${v:,.0f}")

    lines: list[str] = []
    lines.append("# Q4 — Seasonality of demand & revenue per city")
    lines.append("")
    lines.append("**Question.** How does seasonality affect revenue in each city? Is demand stable year-round or concentrated in peak months?")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("- We stream `data/processed/calendar_all_cleaned.csv` (~3 GB) in chunks and aggregate")
    lines.append(f"  per (city, year-month) — chunk size = {CHUNK_ROWS:,} rows.")
    lines.append(f"- **Partial-month filter**: months whose row count is below {PARTIAL_THRESHOLD:.0%} of")
    lines.append("  the city's largest month are dropped. The Inside Airbnb snapshot was scraped in")
    lines.append("  Sept 2025, so the first and last month per city are partial; keeping them would")
    lines.append("  bias the seasonality strength downward (low demand because few days were observed).")
    lines.append("- `demand_proxy` = 1 − mean(available)")
    lines.append("- `median_listing_price` = constant per city, taken from the cleaned `master_data.csv`.")
    lines.append("  The Inside Airbnb calendar leaves `price`/`adjusted_price` empty (documented in the")
    lines.append("  calendar cleaning memo), so we cannot estimate per-month price seasonality from the")
    lines.append("  snapshot — only demand seasonality.")
    lines.append("- `revenue_per_listing` = `demand_proxy × median_listing_price × days_in_month`")
    lines.append("- Seasonality strength: coefficient of variation (CV = std / mean across months).")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- Most seasonal revenue: **{most_seasonal}** (revenue CV = {per_city.loc[most_seasonal, 'revenue_cv']:.2f}).")
    lines.append(f"- Most stable revenue: **{least_seasonal}** (revenue CV = {per_city.loc[least_seasonal, 'revenue_cv']:.2f}).")
    lines.append("")
    lines.append("## Per-city seasonality summary")
    lines.append("")
    lines.append(pc_md.to_markdown())
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append(f"- Monthly metrics CSV: `{rel_monthly}`")
    lines.append(f"- Per-city seasonality CSV: `{rel_summary}`")
    for p in plot_paths:
        lines.append(f"- Figure: `{p.relative_to(PROJECT_ROOT)}`")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    city_price = median_price_per_city()
    monthly = aggregate_calendar(city_price)

    monthly_csv = RESULTS_DIR / "monthly_metrics.csv"
    monthly.to_csv(monthly_csv, index=False)
    print(f"\nSaved {monthly_csv.relative_to(PROJECT_ROOT)}")
    print(f"  rows = {len(monthly):,} (city × year_month)")

    per_city = per_city_seasonality(monthly)
    summary_csv = RESULTS_DIR / "per_city_seasonality.csv"
    per_city.to_csv(summary_csv)
    print(f"Saved {summary_csv.relative_to(PROJECT_ROOT)}")
    print(per_city[["demand_mean", "demand_cv", "revenue_mean",
                    "revenue_cv", "revenue_peak_month",
                    "revenue_peak_to_low"]])

    mba._data_store["q4_monthly"] = monthly
    print("\nToolkit summary on per-month metrics:")
    info = mba.get_summary_statistics(
        dataset_name="q4_monthly",
        columns=["demand_proxy", "median_listing_price", "revenue_per_listing"],
    )
    if info["status"] == "success":
        for col, stats in info["statistics"].items():
            print(f"  {col}: mean={stats.get('mean'):.2f}  median={stats.get('50%'):.2f}")

    p1 = plot_monthly_demand(monthly)
    p2 = plot_monthly_revenue(monthly)
    p3 = plot_seasonality_strength(per_city)
    print(f"\nSaved figures:\n  {p1.relative_to(PROJECT_ROOT)}\n  {p2.relative_to(PROJECT_ROOT)}\n  {p3.relative_to(PROJECT_ROOT)}")

    md = write_markdown(monthly, per_city, monthly_csv, summary_csv, [p1, p2, p3])
    print(f"\nSaved memo: {md.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
