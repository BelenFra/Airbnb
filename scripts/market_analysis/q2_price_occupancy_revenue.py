"""Q2 — How do average nightly prices, occupancy rates and estimated annual
revenues compare across the five cities?

Inputs
------
- ``data/processed/master_data.csv``

Outputs
-------
- ``results/01_market_analysis/q2_price_occupancy_revenue/per_city_summary.csv``
- ``results/01_market_analysis/q2_price_occupancy_revenue/q2_summary.md``
- ``reports/figures/01_market_analysis/q2_price_occupancy_revenue/01_q2_price_distribution.png``
- ``reports/figures/01_market_analysis/q2_price_occupancy_revenue/02_q2_occupancy_distribution.png``
- ``reports/figures/01_market_analysis/q2_price_occupancy_revenue/03_q2_three_metric_comparison.png``

Toolkit usage (per AGENTS.md rule #1)
-------------------------------------
- ``load_data`` for the master dataset
- ``get_summary_statistics`` for headline numbers
- ``create_visualization(viz_type="boxplot", ...)`` for the price and occupancy boxplots

Toolkit gaps handled with plain pandas/matplotlib:
- groupby aggregation per city
- triple grouped bar (price / occupancy / revenue) with three y-axes
- writing CSV and Markdown summaries to ``results/``

Run
---
    .venv/bin/python scripts/market_analysis/q2_price_occupancy_revenue.py
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
RESULTS_DIR = PROJECT_ROOT / "results" / "01_market_analysis" / "q2_price_occupancy_revenue"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "01_market_analysis" / "q2_price_occupancy_revenue"

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
    df["est_annual_revenue"] = df["price_num"] * 365.0 * df["occ"]
    mba._data_store["master"] = df
    return df


# ---------------------------------------------------------------------------
# Per-city summary (toolkit gap: groupby)
# ---------------------------------------------------------------------------

def per_city_summary(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["City", "price_num", "occ", "est_annual_revenue"]
    keep = df[cols].dropna(subset=["City", "price_num", "occ"])

    agg = keep.groupby("City").agg(
        listings=("price_num", "count"),
        mean_price=("price_num", "mean"),
        median_price=("price_num", "median"),
        p25_price=("price_num", lambda s: s.quantile(0.25)),
        p75_price=("price_num", lambda s: s.quantile(0.75)),
        mean_occupancy=("occ", "mean"),
        median_occupancy=("occ", "median"),
        mean_revenue=("est_annual_revenue", "mean"),
        median_revenue=("est_annual_revenue", "median"),
    ).round(2)
    agg = agg.reindex([c for c in CITY_ORDER if c in agg.index])
    agg["mean_price_rank"] = agg["mean_price"].rank(ascending=False).astype(int)
    agg["mean_occupancy_rank"] = agg["mean_occupancy"].rank(ascending=False).astype(int)
    agg["mean_revenue_rank"] = agg["mean_revenue"].rank(ascending=False).astype(int)
    return agg


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_price_distribution(df: pd.DataFrame) -> Path:
    """Price boxplot — clipped at P99 to keep the chart readable."""
    plot_df = df[["City", "price_num"]].dropna()
    plot_df = plot_df[plot_df["price_num"] <= plot_df["price_num"].quantile(0.99)]
    mba._data_store["q2_price"] = plot_df
    info = mba.create_visualization(
        dataset_name="q2_price",
        viz_type="boxplot",
        x_column="City",
        y_column="price_num",
        title="Q2 — nightly price by city",
        save_plot=False,
    )
    if info["status"] != "success":
        raise RuntimeError(f"create_visualization failed: {info}")

    out = FIGURES_DIR / "01_q2_price_distribution.png"
    fig, ax = plt.subplots(figsize=(11, 6))
    cities = [c for c in CITY_ORDER if c in plot_df["City"].unique()]
    data = [plot_df.loc[plot_df["City"] == c, "price_num"].values for c in cities]
    bp = ax.boxplot(data, labels=cities, patch_artist=True, showfliers=False, widths=0.55)
    for patch, c in zip(bp["boxes"], cities):
        patch.set_facecolor(CITY_COLORS[c])
        patch.set_alpha(0.55)
    medians = [np.median(d) for d in data]
    for i, m in enumerate(medians, start=1):
        ax.annotate(f"${m:,.0f}", xy=(i, m), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8, fontweight="bold")
    ax.set_ylabel("Nightly price (USD, P0–P99)")
    ax.set_title("Boxes: IQR; whiskers: 1.5·IQR; outliers above P99 hidden",
                 fontsize=10, color="dimgray", pad=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q2 — Nightly price distribution per city",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_occupancy_distribution(df: pd.DataFrame) -> Path:
    plot_df = df[["City", "occ"]].dropna()
    mba._data_store["q2_occ"] = plot_df
    info = mba.create_visualization(
        dataset_name="q2_occ",
        viz_type="boxplot",
        x_column="City",
        y_column="occ",
        title="Q2 — occupancy by city",
        save_plot=False,
    )
    if info["status"] != "success":
        raise RuntimeError(f"create_visualization failed: {info}")

    out = FIGURES_DIR / "02_q2_occupancy_distribution.png"
    fig, ax = plt.subplots(figsize=(11, 6))
    cities = [c for c in CITY_ORDER if c in plot_df["City"].unique()]
    data = [plot_df.loc[plot_df["City"] == c, "occ"].values for c in cities]
    bp = ax.boxplot(data, labels=cities, patch_artist=True, showfliers=False, widths=0.55)
    for patch, c in zip(bp["boxes"], cities):
        patch.set_facecolor(CITY_COLORS[c])
        patch.set_alpha(0.55)
    medians = [np.median(d) for d in data]
    for i, m in enumerate(medians, start=1):
        ax.annotate(f"{m:.0%}", xy=(i, m), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8, fontweight="bold")
    ax.set_ylabel("Occupancy proxy (1 − availability)")
    ax.set_title("occupancy_rate_proxy = 1 − availability_rate computed in calendar cleaning",
                 fontsize=10, color="dimgray", pad=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q2 — Occupancy distribution per city (proxy)",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_three_metric_comparison(metrics: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "03_q2_three_metric_comparison.png"
    cities = list(metrics.index)
    x = np.arange(len(cities))
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), sharey=False)

    panels = [
        ("Median nightly price", "median_price", "${:,.0f}", lambda v: f"${v:,.0f}"),
        ("Mean occupancy proxy", "mean_occupancy", "{:.0%}", lambda v: f"{v:.0%}"),
        ("Median annual revenue", "median_revenue", "${:,.0f}", lambda v: f"${v/1000:,.0f}k"),
    ]
    for ax, (label, col, lbl_fmt, axis_fmt) in zip(axes, panels):
        bars = ax.bar(x, metrics[col], color=[CITY_COLORS[c] for c in cities],
                      edgecolor="black", alpha=0.85)
        for bar, v in zip(bars, metrics[col]):
            ax.text(bar.get_x() + bar.get_width() / 2, v,
                    "  " + lbl_fmt.format(v), ha="center", va="bottom",
                    fontsize=9, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(cities, rotation=20, ha="right")
        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _, fmt=axis_fmt: fmt(v)))
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.set_ylim(0, max(metrics[col]) * 1.20)

    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.suptitle("Q2 — Price × Occupancy × Revenue across the five cities",
                 fontsize=13, fontweight="bold", y=0.99)
    fig.text(0.5, 0.94,
             "Three medians/means for the same listing population — read all three together",
             ha="center", fontsize=9, color="dimgray")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def write_markdown(metrics: pd.DataFrame, csv_path: Path,
                   plot_paths: list[Path]) -> Path:
    out = RESULTS_DIR / "q2_summary.md"
    rel_csv = csv_path.relative_to(PROJECT_ROOT)

    headline = (
        f"- Most expensive (median nightly): **{metrics['median_price'].idxmax()}** "
        f"(${metrics['median_price'].max():,.0f})\n"
        f"- Highest mean occupancy: **{metrics['mean_occupancy'].idxmax()}** "
        f"({metrics['mean_occupancy'].max():.0%})\n"
        f"- Largest median annual revenue: **{metrics['median_revenue'].idxmax()}** "
        f"(${metrics['median_revenue'].max():,.0f})"
    )

    metrics_md = metrics.copy()
    money = ["mean_price", "median_price", "p25_price", "p75_price",
             "mean_revenue", "median_revenue"]
    for c in money:
        if c in metrics_md.columns:
            metrics_md[c] = metrics_md[c].apply(lambda v: f"${v:,.0f}")
    pct = ["mean_occupancy", "median_occupancy"]
    for c in pct:
        if c in metrics_md.columns:
            metrics_md[c] = metrics_md[c].apply(lambda v: f"{v:.1%}")

    lines: list[str] = []
    lines.append("# Q2 — Price · Occupancy · Revenue across cities")
    lines.append("")
    lines.append("**Question.** How do average nightly prices, occupancy rates and estimated annual revenues compare across the five cities?")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("- One row per cleaned listing in `master_data.csv`.")
    lines.append("- `est_annual_revenue = price × 365 × occupancy_rate_proxy` (consistent across cities).")
    lines.append("- We report mean and median for price, occupancy and revenue per city plus a rank.")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(headline)
    lines.append("")
    lines.append("## Per-city summary")
    lines.append("")
    lines.append(metrics_md.to_markdown())
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append(f"- Per-city summary CSV: `{rel_csv}`")
    for p in plot_paths:
        lines.append(f"- Figure: `{p.relative_to(PROJECT_ROOT)}`")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    df = load_master()

    print("\nToolkit summary (price, occ, revenue):")
    info = mba.get_summary_statistics(
        dataset_name="master",
        columns=["price_num", "occ", "est_annual_revenue"],
    )
    if info["status"] == "success":
        for col, stats in info["statistics"].items():
            print(f"  {col}: median={stats.get('50%')}  mean={stats.get('mean'):.1f}")
    print()

    metrics = per_city_summary(df)
    csv_path = RESULTS_DIR / "per_city_summary.csv"
    metrics.to_csv(csv_path)
    print(f"Saved {csv_path.relative_to(PROJECT_ROOT)}")
    print(metrics[["listings", "median_price", "mean_occupancy",
                   "median_revenue"]])

    p1 = plot_price_distribution(df)
    p2 = plot_occupancy_distribution(df)
    p3 = plot_three_metric_comparison(metrics)
    print(f"\nSaved figures:\n  {p1.relative_to(PROJECT_ROOT)}\n  {p2.relative_to(PROJECT_ROOT)}\n  {p3.relative_to(PROJECT_ROOT)}")

    md = write_markdown(metrics, csv_path, [p1, p2, p3])
    print(f"\nSaved memo: {md.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
