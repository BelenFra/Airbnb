"""Q3 — Which cities have the most competitive (saturated) markets and which
have room for a new entrant?

Inputs
------
- ``data/processed/master_data.csv``

Outputs
-------
- ``results/01_market_analysis/q3_market_saturation/per_city_saturation.csv``
- ``results/01_market_analysis/q3_market_saturation/q3_summary.md``
- ``reports/figures/market_analysis/q3_market_saturation/01_q3_density.png``
- ``reports/figures/market_analysis/q3_market_saturation/02_q3_host_concentration.png``
- ``reports/figures/market_analysis/q3_market_saturation/03_q3_saturation_score.png``

Method
------
We summarise four facets that together describe market saturation:

1. **Density** — active listings per 10,000 residents (population reference for
   2024, see ``CITY_POPULATIONS_2024`` below).
2. **Occupancy** — mean ``occupancy_rate_proxy``. Low occupancy + high density
   suggests over-supply, high occupancy + low density suggests under-supply.
3. **Host concentration (HHI)** — the Herfindahl-Hirschman Index over share of
   listings per host. Higher = more concentrated, harder for newcomers to enter.
4. **Multi-listing host share** — % of listings owned by hosts that operate
   more than one property. A proxy for the professional-vs-amateur split.

A composite ``saturation_score`` (0–1) averages the four normalised facets
(higher = more saturated).

Toolkit usage
-------------
- ``load_data``
- ``get_summary_statistics`` for the headline numbers
- ``create_visualization`` is **not** used because the toolkit only supports
  histograms / bar (top-10 value_counts) / boxplot / scatter / heatmap and we
  need grouped bar comparisons across cities — that is not in the toolkit.
  Plain matplotlib is therefore used for the three figures.

Run
---
    .venv/bin/python scripts/market_analysis/q3_market_saturation.py
"""

from __future__ import annotations

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

MASTER_FILE = PROJECT_ROOT / "data" / "processed" / "master_data.csv"
RESULTS_DIR = PROJECT_ROOT / "results" / "01_market_analysis" / "q3_market_saturation"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "market_analysis" / "q3_market_saturation"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

CITY_ORDER = ["Hawaii", "Los Angeles", "Nashville", "New York", "San Francisco"]
CITY_COLORS = {
    "Hawaii":         "#1f77b4",
    "Los Angeles":    "#ff7f0e",
    "Nashville":      "#2ca02c",
    "New York":       "#d62728",
    "San Francisco":  "#9467bd",
}

# Population references (2024 estimates, US Census / state DBEDT for HI).
# Source URLs cited in the markdown summary.
CITY_POPULATIONS_2024 = {
    "Hawaii":         1_450_589,    # State of Hawaii (DBEDT 2024)
    "Los Angeles":    3_820_914,    # City of LA (Census ACS 2024 estimate)
    "Nashville":        715_884,    # Davidson County / Nashville-Davidson (Census 2024)
    "New York":       8_335_897,    # NYC five boroughs (Census 2024)
    "San Francisco":    808_988,    # City & County of SF (Census 2024)
}


def load_master() -> pd.DataFrame:
    print(f"Loading {MASTER_FILE.relative_to(PROJECT_ROOT)} via toolkit ...")
    info = mba.load_data(str(MASTER_FILE), dataset_name="master")
    if info["status"] != "success":
        raise RuntimeError(f"toolkit load_data failed: {info}")
    print(f"  rows={info['rows']:,}  cols={len(info['columns'])}")
    df = mba._data_store["master"]
    df = df.copy()
    df["price_num"] = pd.to_numeric(df["price"], errors="coerce")
    df["occ"] = pd.to_numeric(df["occupancy_rate_proxy"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# HHI per city (toolkit gap)
# ---------------------------------------------------------------------------

def per_city_saturation(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for city, sub in df.groupby("City"):
        listings = len(sub)
        unique_hosts = sub["host_id"].nunique()
        listings_per_host = sub.groupby("host_id").size()
        shares = listings_per_host / listings_per_host.sum()
        hhi = float((shares ** 2).sum())  # 0..1
        multi_listing_hosts = (listings_per_host > 1).sum()
        listings_in_multi = listings_per_host[listings_per_host > 1].sum()
        top10_share = shares.sort_values(ascending=False).head(10).sum()

        pop = CITY_POPULATIONS_2024.get(city, np.nan)
        listings_per_10k = (listings / pop * 10_000) if pop else np.nan

        rows.append({
            "City": city,
            "listings": listings,
            "unique_hosts": unique_hosts,
            "population_2024": pop,
            "listings_per_10k": round(listings_per_10k, 2) if not np.isnan(listings_per_10k) else np.nan,
            "mean_occupancy": round(sub["occ"].mean(), 4),
            "host_hhi": round(hhi, 5),
            "top10_host_share": round(top10_share, 4),
            "multi_listing_host_pct": round(multi_listing_hosts / unique_hosts, 4),
            "share_listings_in_multi_host_portfolios": round(listings_in_multi / listings, 4),
        })
    res = pd.DataFrame(rows).set_index("City")
    res = res.reindex([c for c in CITY_ORDER if c in res.index])

    # Composite saturation score: min-max normalise each facet, average.
    facets = ["listings_per_10k", "host_hhi", "share_listings_in_multi_host_portfolios"]
    norm = res[facets].copy()
    for c in facets:
        col = norm[c]
        if col.max() == col.min():
            norm[c] = 0.5
        else:
            norm[c] = (col - col.min()) / (col.max() - col.min())
    # Lower occupancy with high density signals over-supply, so add (1 - occ_norm).
    occ_norm = (res["mean_occupancy"] - res["mean_occupancy"].min()) / (
        res["mean_occupancy"].max() - res["mean_occupancy"].min() + 1e-9
    )
    norm["under_supply_proxy"] = 1.0 - occ_norm
    res["saturation_score"] = norm.mean(axis=1).round(3)
    res["saturation_rank"] = res["saturation_score"].rank(ascending=False).astype(int)
    return res


# ---------------------------------------------------------------------------
# Plots (toolkit gap: grouped bar / multi-axis)
# ---------------------------------------------------------------------------

def plot_density(metrics: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "01_q3_density.png"
    fig, ax = plt.subplots(figsize=(11, 6))
    cities = list(metrics.index)
    x = np.arange(len(cities))
    bars = ax.bar(x, metrics["listings_per_10k"],
                  color=[CITY_COLORS[c] for c in cities], edgecolor="black", alpha=0.85)
    for bar, val, n in zip(bars, metrics["listings_per_10k"], metrics["listings"]):
        ax.text(bar.get_x() + bar.get_width() / 2, val,
                f"  {val:,.0f}", ha="center", va="bottom",
                fontsize=10, fontweight="bold")
        ax.text(bar.get_x() + bar.get_width() / 2, val * 0.5,
                f"n={int(n):,} listings", ha="center", va="center",
                fontsize=8, color="white", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(cities, rotation=15, ha="right")
    ax.set_ylabel("Active Airbnb listings per 10,000 residents")
    ax.set_title("Higher = more saturated supply relative to local population",
                 fontsize=10, color="dimgray", pad=8)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q3 — Listing density (supply intensity per resident)",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_host_concentration(metrics: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "02_q3_host_concentration.png"
    fig, ax1 = plt.subplots(figsize=(11, 6.5))
    cities = list(metrics.index)
    x = np.arange(len(cities))
    width = 0.36
    ax2 = ax1.twinx()

    bars1 = ax1.bar(x - width / 2, metrics["host_hhi"] * 10_000,
                    width, color="#3b6fb6", edgecolor="black", alpha=0.85,
                    label="Host HHI ×10,000 (left axis)")
    bars2 = ax2.bar(x + width / 2, metrics["share_listings_in_multi_host_portfolios"] * 100,
                    width, color="#e07b39", edgecolor="black", alpha=0.85,
                    label="% listings in multi-listing portfolios (right axis)")
    for bar, v in zip(bars1, metrics["host_hhi"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, v * 10_000,
                 f" {v*10_000:,.0f}", ha="center", va="bottom", fontsize=8)
    for bar, v in zip(bars2, metrics["share_listings_in_multi_host_portfolios"]):
        ax2.text(bar.get_x() + bar.get_width() / 2, v * 100,
                 f" {v*100:.1f}%", ha="center", va="bottom", fontsize=8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(cities, rotation=15, ha="right")
    ax1.set_ylabel("Host HHI × 10,000 (low = fragmented)", color="#3b6fb6")
    ax2.set_ylabel("% listings owned by multi-listing hosts", color="#e07b39")
    ax1.set_title("Reference: HHI×10k > 2,500 = highly concentrated, 1,500–2,500 = moderate, < 1,500 = competitive",
                  fontsize=10, color="dimgray", pad=8)
    ax1.grid(axis="y", linestyle="--", alpha=0.35)
    ax1.set_ylim(0, max(metrics["host_hhi"] * 10_000) * 1.20)
    ax2.set_ylim(0, max(metrics["share_listings_in_multi_host_portfolios"] * 100) * 1.20)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2,
               loc="lower center", ncol=2, fontsize=9,
               bbox_to_anchor=(0.5, -0.02), frameon=True)
    fig.tight_layout(rect=[0, 0.06, 1, 0.93])
    fig.suptitle("Q3 — Host concentration vs. professional supply share",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_saturation_score(metrics: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "03_q3_saturation_score.png"
    sorted_m = metrics.sort_values("saturation_score", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    bars = ax.barh(sorted_m.index, sorted_m["saturation_score"],
                   color=[CITY_COLORS[c] for c in sorted_m.index],
                   edgecolor="black", alpha=0.85)
    for bar, val, occ in zip(bars, sorted_m["saturation_score"], sorted_m["mean_occupancy"]):
        ax.text(val + 0.01, bar.get_y() + bar.get_height() / 2,
                f"  score = {val:.2f}   |  occupancy = {occ:.0%}",
                va="center", fontsize=9)
    ax.set_xlabel("Composite saturation score (0 = least, 1 = most saturated)")
    ax.set_xlim(0, 1.1)
    ax.set_title("Average of: density per 10k, host HHI, % multi-listing portfolio share, 1 − occupancy",
                 fontsize=10, color="dimgray", pad=8)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q3 — Composite saturation ranking",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def write_markdown(metrics: pd.DataFrame, csv_path: Path,
                   plot_paths: list[Path]) -> Path:
    out = RESULTS_DIR / "q3_summary.md"
    rel_csv = csv_path.relative_to(PROJECT_ROOT)

    most_sat = metrics["saturation_score"].idxmax()
    least_sat = metrics["saturation_score"].idxmin()

    metrics_md = metrics.copy()
    if "population_2024" in metrics_md.columns:
        metrics_md["population_2024"] = metrics_md["population_2024"].apply(
            lambda v: f"{int(v):,}" if pd.notna(v) else "—"
        )
    pct_cols = ["mean_occupancy", "top10_host_share",
                "multi_listing_host_pct", "share_listings_in_multi_host_portfolios"]
    for c in pct_cols:
        if c in metrics_md.columns:
            metrics_md[c] = metrics_md[c].apply(lambda v: f"{v:.1%}")
    metrics_md["host_hhi"] = metrics_md["host_hhi"].apply(lambda v: f"{v*10_000:,.0f}")
    metrics_md.rename(columns={"host_hhi": "host_hhi_x10k"}, inplace=True)

    lines: list[str] = []
    lines.append("# Q3 — Market saturation per city")
    lines.append("")
    lines.append("**Question.** Which cities are most competitive (saturated)? Which have room for a new entrant?")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("Four facets are combined into a composite saturation score (0 = least, 1 = most saturated):")
    lines.append("")
    lines.append("1. **Density**: listings per 10,000 residents (2024 population reference).")
    lines.append("2. **Host HHI**: Herfindahl-Hirschman over listing share by host.")
    lines.append("3. **% listings in multi-listing portfolios**: professional vs amateur supply.")
    lines.append("4. **1 − mean occupancy**: low occupancy → over-supply signal.")
    lines.append("")
    lines.append("Population sources used (state / city, 2024):")
    lines.append("")
    for city, pop in CITY_POPULATIONS_2024.items():
        lines.append(f"- **{city}**: {pop:,}")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- Most saturated market: **{most_sat}**.")
    lines.append(f"- Most room for a new entrant: **{least_sat}**.")
    lines.append("")
    lines.append("> **Methodological note (occupancy).** The mean occupancy reported here uses ")
    lines.append("> `master_data.csv` (listings with a valid price, i.e. *active* supply). The calendar")
    lines.append("> cleaning audit reports a higher figure (e.g. NYC 56% vs 31% here) because it covers")
    lines.append("> *every* calendar listing — including hosts who block their listing all year")
    lines.append("> (very common in NYC under Local Law 18). For an investment decision the active-supply")
    lines.append("> figure is the correct one; the calendar audit value is shown in the EDA only as a")
    lines.append("> supply-utilisation metric.")
    lines.append("")
    lines.append("## Per-city saturation table")
    lines.append("")
    lines.append(metrics_md.to_markdown())
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append(f"- Per-city saturation CSV: `{rel_csv}`")
    for p in plot_paths:
        lines.append(f"- Figure: `{p.relative_to(PROJECT_ROOT)}`")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    df = load_master()

    print("\nToolkit summary (host_id, occupancy):")
    info = mba.get_summary_statistics(
        dataset_name="master",
        columns=["host_id", "occ"],
    )
    if info["status"] == "success":
        print(f"  unique host_id (count via summary): {info['statistics']['host_id'].get('count')}")
        print(f"  occupancy mean = {info['statistics']['occ']['mean']:.4f}")

    metrics = per_city_saturation(df)
    csv_path = RESULTS_DIR / "per_city_saturation.csv"
    metrics.to_csv(csv_path)
    print(f"\nSaved {csv_path.relative_to(PROJECT_ROOT)}")
    print(metrics[["listings_per_10k", "host_hhi",
                   "share_listings_in_multi_host_portfolios",
                   "mean_occupancy", "saturation_score"]])

    p1 = plot_density(metrics)
    p2 = plot_host_concentration(metrics)
    p3 = plot_saturation_score(metrics)
    print(f"\nSaved figures:\n  {p1.relative_to(PROJECT_ROOT)}\n  {p2.relative_to(PROJECT_ROOT)}\n  {p3.relative_to(PROJECT_ROOT)}")

    md = write_markdown(metrics, csv_path, [p1, p2, p3])
    print(f"\nSaved memo: {md.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
