"""Block 2 — Neighborhoods & Segments via K-Means.

Inputs
------
- ``data/master_data_calendar-write-row-files/master_data.csv``
  (one row per listing with `price`, `occupancy_rate_proxy`, `City`,
  `neighbourhood_cleansed`, `room_type`, etc.)

Outputs
-------
- ``results/02_segmentation/cluster_silhouette.csv``
- ``results/02_segmentation/cluster_profiles.csv``
- ``results/02_segmentation/cluster_assignments.csv``
- ``results/02_segmentation/neighborhood_rankings.csv``
- ``results/02_segmentation/segment_supply_demand_gap.csv``
- ``results/02_segmentation/segmentation_summary.md``
- ``reports/figures/02_segmentation/01_elbow_silhouette.png``
- ``reports/figures/02_segmentation/02_cluster_scatter_price_occupancy.png``
- ``reports/figures/02_segmentation/03_cluster_profile_heatmap.png``
- ``reports/figures/02_segmentation/04_neighborhood_ranking_hawaii.png``
- ``reports/figures/02_segmentation/05_supply_demand_gap.png``

Method
------
1. Load `master_data.csv` via the toolkit.
2. Build a 6-dim feature matrix at the listing level:
   `log_price`, `occupancy_rate_proxy`, `accommodates`, `bedrooms`,
   `bathrooms`, `minimum_nights_capped`.
3. `mba.perform_elbow_analysis` (k=2..8) → choose k by silhouette + business
   interpretability (we cap k at 6 to keep clusters explainable).
4. `mba.perform_kmeans_clustering` with the chosen k → attach `cluster` labels.
5. Auto-name clusters via simple rules over their centroid profile.
6. Rank Hawaii neighbourhoods using a composite of revenue, occupancy and a
   "premium gap" (z(price) − z(occupancy)) to flag overpriced/underpriced areas.
7. Compute supply-demand gap per (City, cluster) and per
   (Hawaii neighbourhood, cluster).
8. Write a Markdown memo for the team.

Toolkit usage (per AGENTS.md rule #1)
-------------------------------------
- ``load_data``                      → master dataset
- ``perform_elbow_analysis``         → k selection
- ``perform_kmeans_clustering``      → final clustering
Custom pandas/matplotlib is used for groupby aggregations, neighborhood
scoring, supply/demand metric and figure layout — these are not covered by
the toolkit (analogous to how `q1_risk_adjusted_revenue.py` mixes toolkit
calls with raw aggregations).

Run
---
    python scripts/models/segmentation_kmeans.py
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

MASTER_FILE = PROJECT_ROOT / "data" / "master_data_calendar-write-row-files" / "master_data.csv"
RESULTS_DIR = PROJECT_ROOT / "results" / "02_segmentation"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures" / "02_segmentation"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

TOP_CITY = "Hawaii"  # from Q1 risk-adjusted revenue (median/IQR rank #1)
NUMERIC_FEATURES = [
    "log_price",
    "occupancy_rate_proxy",
    "accommodates",
    "bedrooms",
    "bathrooms",
    "minimum_nights_capped",
]
K_RANGE_MAX = 8
K_BUSINESS_MIN = 4  # k<4 collapses too many segment types into one bucket for the memo
K_BUSINESS_CAP = 6  # k>6 is hard to defend in writing
CLUSTER_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


# ---------------------------------------------------------------------------
# 1. Load + feature engineering
# ---------------------------------------------------------------------------

def load_master() -> pd.DataFrame:
    print(f"Loading {MASTER_FILE.relative_to(PROJECT_ROOT)} via toolkit ...")
    info = mba.load_data(str(MASTER_FILE), dataset_name="seg")
    if info["status"] != "success":
        raise RuntimeError(f"toolkit load_data failed: {info}")
    print(f"  rows={info['rows']:,}  cols={len(info['columns'])}")
    return mba._data_store["seg"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with cleaned numeric features and rows we can cluster on."""
    out = df.copy()

    # Numeric coercion for fields that may have come in as strings.
    for col in ["price", "occupancy_rate_proxy", "accommodates",
                "bedrooms", "bathrooms", "minimum_nights"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # Sanity bounds (drop or cap; keep audit-trail style filtering simple).
    out = out[(out["price"].between(10, 10_000, inclusive="both"))]
    out = out[(out["occupancy_rate_proxy"].between(0, 1, inclusive="both"))]
    out = out[(out["accommodates"].between(1, 16, inclusive="both"))]

    out["log_price"] = np.log1p(out["price"])
    # Right-skewed long-term stays dominate distance otherwise.
    out["minimum_nights_capped"] = out["minimum_nights"].clip(lower=1, upper=30)

    # bedrooms / bathrooms: small portion missing — fill with city-level median
    for col in ["bedrooms", "bathrooms"]:
        med_by_city = out.groupby("City")[col].transform("median")
        out[col] = out[col].fillna(med_by_city)
    out = out.dropna(subset=NUMERIC_FEATURES)

    print(f"After feature build: {len(out):,} listings retained "
          f"({len(df) - len(out):,} dropped on bounds/NaN)")
    return out


# ---------------------------------------------------------------------------
# 2. Elbow / silhouette via the toolkit
# ---------------------------------------------------------------------------

def run_elbow(df_features: pd.DataFrame) -> pd.DataFrame:
    """Use the toolkit's elbow analysis on 2..K_RANGE_MAX."""
    mba._data_store["seg_features"] = df_features[NUMERIC_FEATURES].copy()
    print(f"Running toolkit elbow analysis on k=2..{K_RANGE_MAX} ...")
    info = mba.perform_elbow_analysis(
        dataset_name="seg_features",
        features=NUMERIC_FEATURES,
        max_k=K_RANGE_MAX,
        save_plot=False,
    )
    if info["status"] != "success":
        raise RuntimeError(f"perform_elbow_analysis failed: {info}")
    sil = pd.DataFrame({
        "k": list(info["inertias"].keys()),
        "inertia": list(info["inertias"].values()),
        "silhouette": list(info["silhouette_scores"].values()),
    })
    print(sil.to_string(index=False))
    print(f"Toolkit-recommended k (max silhouette): {info['recommended_k']}")
    return sil


def choose_k(sil_df: pd.DataFrame) -> int:
    """Pick k by silhouette but constrain to [K_BUSINESS_MIN, K_BUSINESS_CAP].

    The unconstrained max often lands at k=2 because the price tail dominates,
    which collapses every other segment ("studio", "family", "long-stay") into
    one bucket — useless for the Block 2 memo. Within the business band the
    silhouette differences are typically <0.02, so we trade a touch of
    statistical separation for actionable segments.
    """
    eligible = sil_df[(sil_df["k"] >= K_BUSINESS_MIN) & (sil_df["k"] <= K_BUSINESS_CAP)]
    chosen = int(eligible.loc[eligible["silhouette"].idxmax(), "k"])
    unconstrained = int(sil_df.loc[sil_df["silhouette"].idxmax(), "k"])
    print(f"Chosen k for final K-Means: {chosen} "
          f"(business band [{K_BUSINESS_MIN},{K_BUSINESS_CAP}]; "
          f"unconstrained-best k={unconstrained})")
    return chosen


def plot_elbow(sil_df: pd.DataFrame, chosen_k: int) -> Path:
    out = FIGURES_DIR / "01_elbow_silhouette.png"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
    ax1.plot(sil_df["k"], sil_df["inertia"], "o-", color="#1f77b4", linewidth=2)
    ax1.axvline(chosen_k, color="red", linestyle="--", alpha=0.6, label=f"chosen k = {chosen_k}")
    ax1.set_xlabel("k (number of clusters)")
    ax1.set_ylabel("Inertia (lower = tighter clusters)")
    ax1.set_title("Elbow plot — within-cluster sum of squares")
    ax1.grid(linestyle="--", alpha=0.35)
    ax1.legend(loc="upper right", fontsize=9)

    ax2.plot(sil_df["k"], sil_df["silhouette"], "o-", color="#d62728", linewidth=2)
    ax2.axvline(chosen_k, color="red", linestyle="--", alpha=0.6, label=f"chosen k = {chosen_k}")
    ax2.set_xlabel("k (number of clusters)")
    ax2.set_ylabel("Silhouette score (higher = better separation)")
    ax2.set_title("Silhouette score by k")
    ax2.grid(linestyle="--", alpha=0.35)
    ax2.legend(loc="upper right", fontsize=9)

    fig.suptitle("Block 2 — choosing the number of segments (k)", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 3. Final K-Means + cluster naming
# ---------------------------------------------------------------------------

def run_kmeans(df_features: pd.DataFrame, k: int) -> pd.Series:
    """Run toolkit's K-Means and return a labels Series aligned to df_features.index."""
    feat_only = df_features[NUMERIC_FEATURES].copy()
    feat_only.index = df_features.index
    mba._data_store["seg_features"] = feat_only.copy()
    info = mba.perform_kmeans_clustering(
        dataset_name="seg_features",
        n_clusters=k,
        features=NUMERIC_FEATURES,
        save_model_as="kmeans_seg",
    )
    if info["status"] != "success":
        raise RuntimeError(f"perform_kmeans_clustering failed: {info}")
    print(f"K-Means done. silhouette={info['silhouette_score']:.4f} "
          f"({info['interpretation']})")
    print(f"Cluster sizes: {info['cluster_sizes']}")
    labels = mba._data_store["seg_features"]["cluster"]
    labels.index = feat_only.index
    return labels


def cluster_profile_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per-cluster business profile."""
    g = df.groupby("cluster")
    profile = pd.DataFrame({
        "n_listings": g.size(),
        "median_price": g["price"].median().round(0),
        "mean_price": g["price"].mean().round(0),
        "median_occupancy": g["occupancy_rate_proxy"].median().round(3),
        "mean_occupancy": g["occupancy_rate_proxy"].mean().round(3),
        "median_accommodates": g["accommodates"].median(),
        "median_bedrooms": g["bedrooms"].median(),
        "median_bathrooms": g["bathrooms"].median(),
        "median_min_nights": g["minimum_nights"].median(),
    })
    profile["est_annual_revenue_proxy"] = (
        profile["median_price"] * profile["median_occupancy"] * 365
    ).round(0)
    profile["share_pct"] = (profile["n_listings"] / profile["n_listings"].sum() * 100).round(1)

    top_room_type = g["room_type"].agg(
        lambda s: s.value_counts(dropna=True).index[0] if s.notna().any() else "—"
    )
    top_city = g["City"].agg(
        lambda s: s.value_counts(dropna=True).index[0] if s.notna().any() else "—"
    )
    profile["top_room_type"] = top_room_type
    profile["top_city"] = top_city
    profile["cluster_name"] = profile.apply(_auto_name_cluster, axis=1)
    profile = profile.sort_values("median_price")
    return profile


def _auto_name_cluster(row: pd.Series) -> str:
    """Translate a cluster centroid into a short business label.

    Rules are heuristic — they exist so the team has a starting label to
    rename in the memo if needed.
    """
    price = float(row["median_price"])
    occ = float(row["median_occupancy"])
    bedrooms = float(row["median_bedrooms"])
    accommodates = float(row["median_accommodates"])
    min_nights = float(row["median_min_nights"])

    if min_nights >= 25:
        return "Long-stay focused"
    if price >= 400 and bedrooms >= 3:
        return "Luxury large home"
    if price >= 250:
        return "Premium mid-size"
    if accommodates <= 2 and price < 150 and occ >= 0.4:
        return "Budget high-occupancy studio"
    if 2 <= bedrooms <= 3 and price < 250:
        return "Mid-price family"
    if accommodates <= 2 and price < 150:
        return "Budget studio low-demand"
    return "General mid-tier"


# ---------------------------------------------------------------------------
# 4. Neighborhood ranking + premium gap (Hawaii)
# ---------------------------------------------------------------------------

def neighborhood_ranking(df: pd.DataFrame, city: str, min_listings: int = 30) -> pd.DataFrame:
    sub = df[df["City"] == city].copy()
    sub["est_annual_revenue_proxy"] = sub["price"] * sub["occupancy_rate_proxy"] * 365
    g = sub.groupby("neighbourhood_cleansed")
    nb = pd.DataFrame({
        "n_listings": g.size(),
        "median_price": g["price"].median(),
        "median_occupancy": g["occupancy_rate_proxy"].median(),
        "median_revenue": g["est_annual_revenue_proxy"].median(),
        "p75_revenue": g["est_annual_revenue_proxy"].quantile(0.75),
    })
    nb = nb[nb["n_listings"] >= min_listings].copy()

    for c in ["median_price", "median_occupancy", "median_revenue"]:
        z = (nb[c] - nb[c].mean()) / nb[c].std(ddof=0)
        nb[f"z_{c}"] = z.round(3)

    # Composite score weights revenue, occupancy and tilts away from over-supply.
    nb["composite_score"] = (
        0.5 * nb["z_median_revenue"]
        + 0.3 * nb["z_median_occupancy"]
        + 0.2 * nb["z_median_price"]
    ).round(3)
    nb["premium_gap"] = (nb["z_median_price"] - nb["z_median_occupancy"]).round(3)
    nb = nb.sort_values("composite_score", ascending=False)
    nb["rank"] = np.arange(1, len(nb) + 1)
    return nb


# ---------------------------------------------------------------------------
# 5. Supply / demand gap per (city, cluster)
# ---------------------------------------------------------------------------

def supply_demand_gap(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["City", "cluster"])
    out = pd.DataFrame({
        "n_listings": g.size(),
        "median_occupancy": g["occupancy_rate_proxy"].median(),
    }).reset_index()
    by_city_total = out.groupby("City")["n_listings"].transform("sum")
    out["supply_share_in_city"] = (out["n_listings"] / by_city_total).round(3)

    median_occ_overall = out["median_occupancy"].median()
    median_supply_overall = out["supply_share_in_city"].median()

    def classify(row: pd.Series) -> str:
        hot = row["median_occupancy"] >= median_occ_overall
        crowded = row["supply_share_in_city"] >= median_supply_overall
        if hot and crowded:
            return "Hot & crowded — competitive"
        if hot and not crowded:
            return "Underserved — opportunity"
        if not hot and crowded:
            return "Oversupplied — risk"
        return "Cold & thin — niche"

    out["status"] = out.apply(classify, axis=1)
    return out.sort_values(["City", "median_occupancy"], ascending=[True, False])


# ---------------------------------------------------------------------------
# 6. Figures
# ---------------------------------------------------------------------------

def plot_cluster_scatter(df: pd.DataFrame, profile: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "02_cluster_scatter_price_occupancy.png"
    fig, ax = plt.subplots(figsize=(11, 7))
    sample = df.sample(n=min(20_000, len(df)), random_state=RANDOM_STATE)
    cluster_to_name = profile["cluster_name"].to_dict()
    for ci, cl in enumerate(sorted(sample["cluster"].unique())):
        d = sample[sample["cluster"] == cl]
        ax.scatter(d["price"], d["occupancy_rate_proxy"],
                   s=8, alpha=0.35,
                   color=CLUSTER_PALETTE[ci % len(CLUSTER_PALETTE)],
                   label=f"{cl}: {cluster_to_name.get(cl, '—')} (n={(df['cluster']==cl).sum():,})")
    ax.set_xscale("log")
    ax.set_xlabel("Listing price (USD/night, log scale)")
    ax.set_ylabel("Occupancy rate proxy (1 − availability)")
    ax.set_title("Block 2 — listing segments in the price × occupancy plane (sample of 20k)",
                 fontsize=10, color="dimgray", pad=8)
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", fontsize=8, markerscale=2)
    fig.suptitle("Listing segments — price vs. occupancy", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_cluster_heatmap(df_features: pd.DataFrame, df_full: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "03_cluster_profile_heatmap.png"
    feats = df_full.loc[df_features.index, NUMERIC_FEATURES + ["cluster"]].copy()
    z = (feats[NUMERIC_FEATURES] - feats[NUMERIC_FEATURES].mean()) / feats[NUMERIC_FEATURES].std(ddof=0)
    z["cluster"] = feats["cluster"]
    profile_z = z.groupby("cluster")[NUMERIC_FEATURES].mean()

    fig, ax = plt.subplots(figsize=(9, 0.8 + 0.45 * len(profile_z)))
    im = ax.imshow(profile_z.values, aspect="auto", cmap="RdBu_r",
                   vmin=-2.0, vmax=2.0)
    ax.set_xticks(np.arange(len(NUMERIC_FEATURES)))
    ax.set_xticklabels(NUMERIC_FEATURES, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(profile_z)))
    ax.set_yticklabels([f"cluster {i}" for i in profile_z.index])
    for i in range(profile_z.shape[0]):
        for j in range(profile_z.shape[1]):
            ax.text(j, i, f"{profile_z.values[i, j]:+.1f}",
                    ha="center", va="center",
                    color="black" if abs(profile_z.values[i, j]) < 1.2 else "white",
                    fontsize=8)
    fig.colorbar(im, ax=ax, label="Standardised feature z-score")
    ax.set_title("Block 2 — cluster profile (mean z-score per feature)",
                 fontsize=12, fontweight="bold", pad=10)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_neighborhood_ranking(nb_rank: pd.DataFrame, city: str) -> Path:
    out = FIGURES_DIR / "04_neighborhood_ranking_hawaii.png"
    top = nb_rank.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in top["composite_score"]]
    bars = ax.barh(top.index, top["composite_score"], color=colors, alpha=0.85,
                   edgecolor="black")
    for bar, val, n in zip(bars, top["composite_score"], top["n_listings"]):
        ax.text(val + (0.03 if val >= 0 else -0.03),
                bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}  (n={int(n):,})",
                va="center",
                ha="left" if val >= 0 else "right",
                fontsize=9)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Composite score (z-weighted: 0.5 revenue + 0.3 occupancy + 0.2 price)")
    ax.set_title(f"Top 15 {city} neighborhoods by composite investment score (positive = above city average)",
                 fontsize=10, color="dimgray", pad=8)
    fig.suptitle(f"Block 2 — {city} neighborhood ranking", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_supply_demand(sd: pd.DataFrame, profile: pd.DataFrame) -> Path:
    out = FIGURES_DIR / "05_supply_demand_gap.png"
    cluster_names = profile["cluster_name"].to_dict()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    status_color = {
        "Hot & crowded — competitive": "#1f77b4",
        "Underserved — opportunity": "#2ca02c",
        "Oversupplied — risk": "#d62728",
        "Cold & thin — niche": "#7f7f7f",
    }
    for status, color in status_color.items():
        d = sd[sd["status"] == status]
        ax.scatter(d["supply_share_in_city"], d["median_occupancy"],
                   s=80 + d["n_listings"] / 100,
                   color=color, alpha=0.7, edgecolor="black",
                   label=status, zorder=3)
    for _, row in sd.iterrows():
        ax.annotate(f"{row['City'][:3]}-c{int(row['cluster'])}",
                    (row["supply_share_in_city"], row["median_occupancy"]),
                    fontsize=8, alpha=0.7, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("Supply share within city (= cluster's % of city listings)")
    ax.set_ylabel("Median occupancy proxy (cluster within city)")
    ax.set_title(f"Bubble size ∝ listings count. Clusters: " +
                 ", ".join([f"c{k}={v}" for k, v in cluster_names.items()]),
                 fontsize=9, color="dimgray", pad=8)
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", fontsize=9)
    fig.suptitle("Block 2 — supply-demand gap per (city × segment)", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# 7. Markdown memo
# ---------------------------------------------------------------------------

def write_summary(profile: pd.DataFrame, sil: pd.DataFrame, chosen_k: int,
                  nb_rank: pd.DataFrame, sd: pd.DataFrame,
                  fig_paths: list[Path]) -> Path:
    out = RESULTS_DIR / "segmentation_summary.md"
    rel_figs = [p.relative_to(PROJECT_ROOT) for p in fig_paths]

    lines: list[str] = []
    lines.append("# Block 2 — Neighborhoods & Segments (K-Means)")
    lines.append("")
    lines.append("**Question.** Within the top city (Hawaii — see Q1), which neighborhoods "
                 "and listing segments offer the strongest risk-return profile?")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append("- Clustering features (per listing): "
                 f"`{', '.join(NUMERIC_FEATURES)}`.")
    lines.append("- Standardised, then `mba706_toolkit.perform_kmeans_clustering` "
                 "(scipy `kmeans2`, k++ init, `RANDOM_STATE=42`).")
    lines.append(f"- k chosen via `mba706_toolkit.perform_elbow_analysis`, capped at "
                 f"{K_BUSINESS_CAP} for business explainability → final **k = {chosen_k}**.")
    lines.append("- Neighborhood ranking (Hawaii only): composite z-score "
                 "= 0.5·revenue + 0.3·occupancy + 0.2·price (≥30 listings only).")
    lines.append("- Supply-demand gap: per (city, cluster), classify by `median occupancy` "
                 "vs `supply share` against the cross-city medians.")
    lines.append("")
    lines.append("## k selection (silhouette + inertia)")
    lines.append("")
    lines.append(sil.to_markdown(index=False))
    lines.append("")
    lines.append("## Cluster profiles")
    lines.append("")
    profile_md = profile.copy()
    profile_md["median_price"] = profile_md["median_price"].apply(lambda v: f"${v:,.0f}")
    profile_md["mean_price"] = profile_md["mean_price"].apply(lambda v: f"${v:,.0f}")
    profile_md["est_annual_revenue_proxy"] = profile_md["est_annual_revenue_proxy"].apply(
        lambda v: f"${v:,.0f}")
    profile_md["median_occupancy"] = profile_md["median_occupancy"].apply(lambda v: f"{v:.1%}")
    profile_md["mean_occupancy"] = profile_md["mean_occupancy"].apply(lambda v: f"{v:.1%}")
    lines.append(profile_md.reset_index().to_markdown(index=False))
    lines.append("")
    lines.append("## Top-10 Hawaii neighborhoods (composite score)")
    lines.append("")
    nb_top = nb_rank.head(10).copy()
    for c in ["median_price", "median_revenue", "p75_revenue"]:
        nb_top[c] = nb_top[c].apply(lambda v: f"${v:,.0f}")
    nb_top["median_occupancy"] = nb_top["median_occupancy"].apply(lambda v: f"{v:.1%}")
    keep = ["rank", "n_listings", "median_price", "median_occupancy",
            "median_revenue", "p75_revenue",
            "z_median_revenue", "z_median_occupancy", "z_median_price",
            "premium_gap", "composite_score"]
    nb_top_view = nb_top[keep]
    lines.append(nb_top_view.reset_index().to_markdown(index=False))
    lines.append("")
    lines.append("> **`premium_gap` reading:** positive = neighborhood is priced above the "
                 "city average more than its occupancy supports → over-priced; "
                 "negative = under-priced relative to demand → potential pricing power.")
    lines.append("")
    lines.append("## Supply-demand status (per city × segment)")
    lines.append("")
    sd_md = sd.copy()
    sd_md["median_occupancy"] = sd_md["median_occupancy"].apply(lambda v: f"{v:.1%}")
    sd_md["supply_share_in_city"] = sd_md["supply_share_in_city"].apply(lambda v: f"{v:.1%}")
    lines.append(sd_md.to_markdown(index=False))
    lines.append("")
    lines.append("## Figures")
    lines.append("")
    for p in rel_figs:
        lines.append(f"- `{p}`")
    lines.append("")
    lines.append("## Hand-off to Block 5 (Investment Decision)")
    lines.append("")
    top_seg = profile.sort_values("est_annual_revenue_proxy", ascending=False).head(2)
    top_nb = nb_rank.head(3).index.tolist()
    lines.append(f"- Recommended **segments to short-list**: "
                 + ", ".join([f"`{cn}` (cluster {idx})"
                              for idx, cn in top_seg["cluster_name"].items()])
                 + ".")
    lines.append(f"- Recommended **Hawaii neighborhoods to short-list**: "
                 + ", ".join(f"`{n}`" for n in top_nb) + ".")
    lines.append("- Use `cluster_assignments.csv` as the join key for Block 5 "
                 "(`listing_id, City, cluster, cluster_name`).")
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = load_master()
    df_features = build_features(df)

    sil = run_elbow(df_features)
    sil_path = RESULTS_DIR / "cluster_silhouette.csv"
    sil.to_csv(sil_path, index=False)
    print(f"Saved {sil_path.relative_to(PROJECT_ROOT)}")

    chosen_k = choose_k(sil)
    fig_elbow = plot_elbow(sil, chosen_k)

    labels = run_kmeans(df_features, chosen_k)
    df_features["cluster"] = labels.astype(int)

    profile = cluster_profile_table(df_features)
    profile_path = RESULTS_DIR / "cluster_profiles.csv"
    profile.to_csv(profile_path)
    print(f"Saved {profile_path.relative_to(PROJECT_ROOT)}")
    print(profile[["cluster_name", "n_listings", "share_pct",
                   "median_price", "median_occupancy", "est_annual_revenue_proxy"]])

    assignments = df_features[["id", "City", "neighbourhood_cleansed",
                               "room_type", "cluster"]].copy()
    assignments = assignments.rename(columns={"id": "listing_id"})
    assignments["cluster_name"] = assignments["cluster"].map(profile["cluster_name"].to_dict())
    assn_path = RESULTS_DIR / "cluster_assignments.csv"
    assignments.to_csv(assn_path, index=False)
    print(f"Saved {assn_path.relative_to(PROJECT_ROOT)}")

    nb_rank = neighborhood_ranking(df_features, TOP_CITY)
    nb_path = RESULTS_DIR / "neighborhood_rankings.csv"
    nb_rank.to_csv(nb_path)
    print(f"Saved {nb_path.relative_to(PROJECT_ROOT)}")

    sd = supply_demand_gap(df_features)
    sd_path = RESULTS_DIR / "segment_supply_demand_gap.csv"
    sd.to_csv(sd_path, index=False)
    print(f"Saved {sd_path.relative_to(PROJECT_ROOT)}")

    fig_scatter = plot_cluster_scatter(df_features, profile)
    fig_heatmap = plot_cluster_heatmap(df_features, df_features)
    fig_nb = plot_neighborhood_ranking(nb_rank, TOP_CITY)
    fig_sd = plot_supply_demand(sd, profile)

    md = write_summary(profile, sil, chosen_k, nb_rank, sd,
                       [fig_elbow, fig_scatter, fig_heatmap, fig_nb, fig_sd])
    print(f"\nSaved memo: {md.relative_to(PROJECT_ROOT)}")
    print("\nBlock 2 done. Outputs under results/02_segmentation/ and "
          "reports/figures/02_segmentation/.")


if __name__ == "__main__":
    main()
