"""Q1 — Which city offers the best risk-adjusted revenue opportunity?

Inputs
------
- ``data/processed/master_data.csv`` (one row per listing with
  ``price``, ``occupancy_rate_proxy`` and ``City``)

Outputs
-------
- ``results/01_market_analysis/q1_risk_adjusted_revenue/per_city_metrics.csv``
- ``results/01_market_analysis/q1_risk_adjusted_revenue/q1_summary.md``
- ``reports/figures/01_market_analysis/q1_risk_adjusted_revenue/01_q1_revenue_boxplot.png``
- ``reports/figures/01_market_analysis/q1_risk_adjusted_revenue/02_q1_sharpe_ranking.png``
- ``reports/figures/01_market_analysis/q1_risk_adjusted_revenue/03_q1_return_vs_risk.png``

Method
------
For each listing we estimate the annual revenue as
``annual_revenue = price * 365 * occupancy_rate_proxy``.
Per city we report central tendency (median, mean), dispersion (std, IQR, P10..P90)
and a Sharpe-style ratio ``mean / std`` that rewards cities with high typical
revenue and low cross-listing variance.

NOTE: the data does not include a risk-free rate, so this is a *Sharpe-style*
ratio (sometimes called the *coefficient of variation*'s inverse), not the CAPM
Sharpe ratio. We use the median/IQR variant as a robust alternative because the
revenue distribution has heavy right tails.

Toolkit usage (per AGENTS.md rule #1)
-------------------------------------
- ``load_data`` for the master dataset
- ``get_summary_statistics`` for the headline numbers
- ``create_visualization`` for the boxplot

The cross-city aggregation (groupby), Sharpe-style ratios, and CSV/Markdown
writing are not covered by the toolkit, so they use plain pandas/matplotlib.

Run
---
    .venv/bin/python scripts/market_analysis/q1_risk_adjusted_revenue.py
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
RESULTS_DIR = PROJECT_ROOT / "results" / "01_market_analysis" / "q1_risk_adjusted_revenue"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "01_market_analysis" / "q1_risk_adjusted_revenue"

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


# ---------------------------------------------------------------------------
# 1. Load data via the toolkit
# ---------------------------------------------------------------------------

def load_master() -> pd.DataFrame:
    print(f"Loading {MASTER_FILE.relative_to(PROJECT_ROOT)} via toolkit ...")
    info = mba.load_data(str(MASTER_FILE), dataset_name="master")
    if info["status"] != "success":
        raise RuntimeError(f"toolkit load_data failed: {info}")
    print(f"  rows={info['rows']:,}  cols={len(info['columns'])}")
    df = mba._data_store["master"]
    return df


# ---------------------------------------------------------------------------
# 2. Per-listing annual revenue (toolkit gap: simple column derivation)
# ---------------------------------------------------------------------------

def add_estimated_annual_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """``price * 365 * occupancy_rate_proxy`` per listing.

    Why this and not Inside Airbnb's ``estimated_revenue_l365d``? Because for
    New York that field is mostly zero (Local Law 18 caps), so it is unfair
    cross-city. Using ``price * 365 * occupancy`` keeps every city on the same
    methodology even if the absolute level is a proxy.
    """
    df = df.copy()
    df["price_num"] = pd.to_numeric(df["price"], errors="coerce")
    df["occ"] = pd.to_numeric(df["occupancy_rate_proxy"], errors="coerce")
    df["est_annual_revenue"] = df["price_num"] * 365.0 * df["occ"]
    return df


# ---------------------------------------------------------------------------
# 3. Per-city metrics (toolkit gap: groupby aggregations)
# ---------------------------------------------------------------------------

def per_city_metrics(df: pd.DataFrame) -> pd.DataFrame:
    keep = df[["City", "price_num", "occ", "est_annual_revenue"]].dropna(
        subset=["City", "est_annual_revenue"]
    )
    agg = keep.groupby("City").agg(
        listings=("est_annual_revenue", "count"),
        median_price=("price_num", "median"),
        median_occupancy=("occ", "median"),
        mean_revenue=("est_annual_revenue", "mean"),
        median_revenue=("est_annual_revenue", "median"),
        std_revenue=("est_annual_revenue", "std"),
        p10_revenue=("est_annual_revenue", lambda s: s.quantile(0.10)),
        p25_revenue=("est_annual_revenue", lambda s: s.quantile(0.25)),
        p75_revenue=("est_annual_revenue", lambda s: s.quantile(0.75)),
        p90_revenue=("est_annual_revenue", lambda s: s.quantile(0.90)),
    ).round(2)

    agg["iqr_revenue"] = (agg["p75_revenue"] - agg["p25_revenue"]).round(2)
    agg["sharpe_mean_std"] = (agg["mean_revenue"] / agg["std_revenue"]).round(3)
    agg["sharpe_median_iqr"] = (agg["median_revenue"] / agg["iqr_revenue"]).round(3)

    agg = agg.reindex(
        [c for c in CITY_ORDER if c in agg.index]
        + [c for c in agg.index if c not in CITY_ORDER]
    )
    agg["sharpe_mean_std_rank"] = agg["sharpe_mean_std"].rank(ascending=False).astype(int)
    agg["sharpe_median_iqr_rank"] = agg["sharpe_median_iqr"].rank(ascending=False).astype(int)
    return agg


# ---------------------------------------------------------------------------
# 4. Plots
# ---------------------------------------------------------------------------

def plot_revenue_boxplot(df: pd.DataFrame) -> Path:
    """Toolkit ``boxplot`` covers City × est_annual_revenue but adds default
    title styling we want to control, so we wrap it and tweak labels."""
    plot_df = df[["City", "est_annual_revenue"]].dropna()
    plot_df = plot_df[plot_df["est_annual_revenue"] <= plot_df["est_annual_revenue"].quantile(0.99)]

    mba._data_store["q1_box"] = plot_df
    info = mba.create_visualization(
        dataset_name="q1_box",
        viz_type="boxplot",
        x_column="City",
        y_column="est_annual_revenue",
        title="Estimated annual revenue per listing — by city (P0–P99)",
        save_plot=False,
    )
    if info["status"] != "success":
        raise RuntimeError(f"create_visualization failed: {info}")

    out = FIGURES_DIR / "01_q1_revenue_boxplot.png"
    fig, ax = plt.subplots(figsize=(11, 6))
    cities = [c for c in CITY_ORDER if c in plot_df["City"].unique()]
    data = [plot_df.loc[plot_df["City"] == c, "est_annual_revenue"].values for c in cities]
    bp = ax.boxplot(data, labels=cities, patch_artist=True, showfliers=False, widths=0.55)
    for patch, c in zip(bp["boxes"], cities):
        patch.set_facecolor(CITY_COLORS[c])
        patch.set_alpha(0.55)
    medians = [np.median(d) for d in data]
    for i, m in enumerate(medians, start=1):
        ax.annotate(f"${m:,.0f}", xy=(i, m), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8, fontweight="bold", color="black")
    ax.set_ylabel("Estimated annual revenue per listing (USD)")
    ax.set_title("annual_revenue = price · 365 · occupancy_rate_proxy",
                 fontsize=10, color="dimgray", pad=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.suptitle("Q1 — Revenue distribution per listing (P0–P99 to suppress extremes)",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_sharpe_ranking(metrics: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "02_q1_sharpe_ranking.png"
    metrics_sorted = metrics.sort_values("sharpe_median_iqr", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = [CITY_COLORS[c] for c in metrics_sorted.index]
    bars = ax.barh(metrics_sorted.index, metrics_sorted["sharpe_median_iqr"],
                   color=colors, edgecolor="black", alpha=0.85)
    for bar, val, mean_std in zip(bars, metrics_sorted["sharpe_median_iqr"],
                                  metrics_sorted["sharpe_mean_std"]):
        ax.text(val * 0.98, bar.get_y() + bar.get_height() / 2,
                f"median/IQR = {val:.2f}",
                va="center", ha="right", fontsize=10, fontweight="bold",
                color="white")
        ax.text(val + max(metrics_sorted["sharpe_median_iqr"]) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"  mean/std = {mean_std:.2f}",
                va="center", fontsize=9, color="dimgray")
    ax.set_xlabel("Risk-adjusted revenue ratio (median / IQR — higher is better)")
    ax.set_title("Higher = stronger typical revenue per unit of cross-listing dispersion",
                 fontsize=10, color="dimgray", pad=8)
    ax.set_xlim(0, max(metrics_sorted["sharpe_median_iqr"]) * 1.18)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.suptitle("Q1 — Risk-adjusted revenue ranking",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_return_vs_risk(metrics: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "03_q1_return_vs_risk.png"
    fig, ax = plt.subplots(figsize=(12, 8.5))

    # Bubble AREA is proportional to the actual number of active listings
    # (no clipping). matplotlib.scatter `s` is in points^2; we scale linearly
    # so Nashville (n≈5,795) → ~145 pt² and LA (n≈36,819) → ~920 pt².
    bubble_scale = 0.025
    bubble_sizes = metrics["listings"] * bubble_scale

    # Place labels OUTSIDE the bubble. The city goes on the FAR side and the
    # `n=...` goes between the city and the bubble, on the same side.
    label_position = {
        "Hawaii":         "up",
        "Los Angeles":    "down",
        "Nashville":      "up",
        "New York":       "up",
        "San Francisco":  "up",
    }

    for city in metrics.index:
        x = metrics.loc[city, "iqr_revenue"]
        y = metrics.loc[city, "median_revenue"]
        n = int(metrics.loc[city, "listings"])
        size = bubble_sizes.loc[city]
        ax.scatter(x, y, s=size, color=CITY_COLORS[city], alpha=0.55,
                   edgecolor="black", linewidth=1.2, zorder=3)

        radius_pt = np.sqrt(size / np.pi)
        n_gap_pt = radius_pt + 8
        city_gap_pt = radius_pt + 22
        if label_position.get(city, "up") == "up":
            n_y = n_gap_pt
            city_y = city_gap_pt
            va = "bottom"
        else:
            n_y = -n_gap_pt
            city_y = -city_gap_pt
            va = "top"

        ax.annotate(f"n={n:,}", xy=(x, y),
                    xytext=(0, n_y), textcoords="offset points",
                    ha="center", va=va,
                    fontsize=9, color="dimgray", zorder=5)
        ax.annotate(city, xy=(x, y),
                    xytext=(0, city_y), textcoords="offset points",
                    ha="center", va=va,
                    fontsize=11, fontweight="bold", zorder=5)

    if not metrics.empty:
        slope = metrics["median_revenue"].max() / metrics["iqr_revenue"].max()
        xs = np.linspace(0, metrics["iqr_revenue"].max() * 1.05, 50)
        ax.plot(xs, slope * xs, linestyle=":", color="gray", alpha=0.5,
                label="Equal Sharpe (median/IQR)")

    ax.set_xlabel("Cross-listing dispersion (IQR of annual revenue, USD) — risk")
    ax.set_ylabel("Median annual revenue per listing (USD) — return")
    ax.set_title("Bubble area is proportional to the number of active listings; up-left = best risk/return profile",
                 fontsize=10, color="dimgray", pad=8)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    # Extra room above/below for the labels outside the bubbles.
    ax.set_xlim(metrics["iqr_revenue"].min() * 0.55,
                metrics["iqr_revenue"].max() * 1.15)
    ax.set_ylim(metrics["median_revenue"].min() * 0.45,
                metrics["median_revenue"].max() * 1.30)
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.suptitle("Q1 — Return vs. risk per city",
                 fontsize=13, fontweight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 5. Markdown summary
# ---------------------------------------------------------------------------

def write_markdown(metrics: pd.DataFrame, csv_path: Path,
                   plot_paths: list[Path]) -> Path:
    out = RESULTS_DIR / "q1_summary.md"

    best_sharpe = metrics["sharpe_median_iqr"].idxmax()
    best_median = metrics["median_revenue"].idxmax()
    safest = metrics["iqr_revenue"].idxmin()

    rel_csv = csv_path.relative_to(PROJECT_ROOT)
    rel_plots = [p.relative_to(PROJECT_ROOT) for p in plot_paths]

    lines: list[str] = []
    lines.append("# Q1 — Risk-adjusted revenue per city")
    lines.append("")
    lines.append("**Question.** Which city offers the best risk-adjusted revenue opportunity for a new Airbnb investment?")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("- Per-listing annual revenue proxy: `price × 365 × occupancy_rate_proxy`.")
    lines.append("- We use the same formula in every city to keep methodology consistent. ")
    lines.append("  (We do not use Inside Airbnb's `estimated_revenue_l365d` because in NYC it is mostly")
    lines.append("  zero due to Local Law 18 caps and would penalise NYC unfairly.)")
    lines.append("- *Risk-adjusted* metrics:")
    lines.append("  - **Sharpe-style (mean / std)** — classic, sensitive to outliers.")
    lines.append("  - **median / IQR** — robust alternative, recommended for the long-tailed revenue distribution.")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("")
    metrics_md = metrics.copy()
    money_cols = [c for c in metrics_md.columns if "revenue" in c or "price" in c]
    for c in money_cols:
        metrics_md[c] = metrics_md[c].apply(lambda v: f"${v:,.0f}" if pd.notna(v) else "—")
    metrics_md["median_occupancy"] = metrics_md["median_occupancy"].apply(
        lambda v: f"{v:.1%}" if pd.notna(v) else "—"
    )
    lines.append(metrics_md.to_markdown())
    lines.append("")
    lines.append("## Business reading")
    lines.append("")
    lines.append(f"- **Best risk-adjusted (median / IQR): {best_sharpe}** — highest typical revenue per unit of cross-listing dispersion.")
    lines.append(f"- **Highest typical revenue (median): {best_median}**.")
    lines.append(f"- **Most homogeneous market (smallest IQR): {safest}** — risk is lowest but absolute returns may be smaller.")
    lines.append("")
    lines.append("> **Why median, not mean?** The mean revenue is distorted by extreme listings (e.g.")
    lines.append("> Hawaii's `price` reaches $85,000 on luxury villas). For Hawaii ``mean_revenue`` is")
    lines.append("> ~7× the median, which is why we report median + IQR as the headline robustness")
    lines.append("> metric and keep `sharpe_mean_std` only as a secondary cross-check.")
    lines.append("")
    lines.append("Use the **return vs. risk** scatter (Plot 3) to weigh the trade-off; ")
    lines.append("a city in the top-left (high median, low IQR) is the prime candidate.")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append(f"- Per-city metrics CSV: `{rel_csv}`")
    for p in rel_plots:
        lines.append(f"- Figure: `{p}`")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = load_master()

    print("\nToolkit summary (price, occupancy):")
    info = mba.get_summary_statistics(
        dataset_name="master",
        columns=["price", "occupancy_rate_proxy"],
    )
    if info["status"] == "success":
        for col, stats in info["statistics"].items():
            print(f"  {col}:")
            for k, v in stats.items():
                print(f"    {k}: {v}")
    print()

    df = add_estimated_annual_revenue(df)
    mba._data_store["master"] = df

    metrics = per_city_metrics(df)
    csv_path = RESULTS_DIR / "per_city_metrics.csv"
    metrics.to_csv(csv_path)
    print(f"Saved {csv_path.relative_to(PROJECT_ROOT)}")
    print(metrics[["listings", "median_revenue", "iqr_revenue",
                   "sharpe_mean_std", "sharpe_median_iqr"]])

    p1 = plot_revenue_boxplot(df)
    p2 = plot_sharpe_ranking(metrics)
    p3 = plot_return_vs_risk(metrics)
    print(f"\nSaved figures:\n  {p1.relative_to(PROJECT_ROOT)}\n  {p2.relative_to(PROJECT_ROOT)}\n  {p3.relative_to(PROJECT_ROOT)}")

    md = write_markdown(metrics, csv_path, [p1, p2, p3])
    print(f"\nSaved memo: {md.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
