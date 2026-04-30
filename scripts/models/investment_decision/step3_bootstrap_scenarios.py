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

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from mba706_toolkit import execute_python_code, get_column_info, get_summary_statistics, load_data


def main() -> None:
    listing_metrics_path = PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step1_budget_feasible_listing_metrics.csv"
    top_segments_path = PROJECT_ROOT / "results" / "investment_decision" / "step1_top_candidate_segments.csv"
    knn_summary_path = PROJECT_ROOT / "results" / "investment_decision" / "step2_knn_candidate_validation_summary.csv"

    listing_result = load_data(str(listing_metrics_path), dataset_name="step1_listing_metrics")
    if listing_result.get("status") != "success":
        raise RuntimeError(listing_result)

    segment_result = load_data(str(top_segments_path), dataset_name="step1_top_segments")
    if segment_result.get("status") != "success":
        raise RuntimeError(segment_result)

    knn_result = load_data(str(knn_summary_path), dataset_name="step2_knn_summary")
    if knn_result.get("status") != "success":
        raise RuntimeError(knn_result)

    get_column_info("step1_listing_metrics")
    get_summary_statistics(
        "step1_listing_metrics",
        columns=["nightly_price", "occupancy_rate", "annual_revenue", "review_scores_rating"],
    )

    code = r'''
from pathlib import Path

project_root = Path("''' + str(PROJECT_ROOT) + r'''")
processed_dir = project_root / "data" / "processed" / "investment_decision"
results_dir = project_root / "results" / "investment_decision"
reports_dir = project_root / "reports" / "investment_decision"
figures_dir = project_root / "reports" / "figures"
processed_dir.mkdir(parents=True, exist_ok=True)
results_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)
figures_dir.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(RANDOM_STATE)
listings = _data_store["step1_listing_metrics"].copy()
segments = _data_store["step1_top_segments"].copy().head(5)
knn = _data_store["step2_knn_summary"].copy()

for frame in [listings, segments, knn]:
    for col in frame.columns:
        if col in [
            "id",
            "bedroom_count",
            "bedrooms",
            "nightly_price",
            "occupancy_rate",
            "annual_revenue",
            "median_nightly_price",
            "median_occupancy_rate",
            "median_annual_revenue",
            "candidate_segment_median_revenue",
            "knn_median_revenue",
            "knn_p25_revenue",
            "knn_p75_revenue",
            "knn_median_price",
            "knn_median_occupancy",
        ]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

scenario_rows = []
bootstrap_rows = []
sensitivity_rows = []

for rank, segment in enumerate(segments.to_dict(orient="records"), start=1):
    candidate_segment = (
        f"{segment['City']} / {segment['neighbourhood_cleansed']} / "
        f"{segment['property_type']} / {int(segment['bedroom_count'])}BR"
    )
    mask = (
        listings["city_key"].eq(segment["city_key"])
        & listings["neighbourhood_cleansed"].eq(segment["neighbourhood_cleansed"])
        & listings["property_type"].eq(segment["property_type"])
        & listings["bedroom_count"].eq(segment["bedroom_count"])
    )
    comps = listings[mask].dropna(subset=["annual_revenue", "nightly_price", "occupancy_rate"]).copy()
    if len(comps) < 25:
        continue

    scenario_rows.extend(
        [
            {
                "candidate_rank": rank,
                "candidate_segment": candidate_segment,
                "source": "segment comps",
                "scenario": "Conservative",
                "basis": "25th percentile of full candidate segment",
                "n": len(comps),
                "nightly_price": comps["nightly_price"].quantile(0.25),
                "occupancy_rate": comps["occupancy_rate"].quantile(0.25),
                "annual_revenue": comps["annual_revenue"].quantile(0.25),
            },
            {
                "candidate_rank": rank,
                "candidate_segment": candidate_segment,
                "source": "segment comps",
                "scenario": "Moderate",
                "basis": "Median of full candidate segment",
                "n": len(comps),
                "nightly_price": comps["nightly_price"].median(),
                "occupancy_rate": comps["occupancy_rate"].median(),
                "annual_revenue": comps["annual_revenue"].median(),
            },
            {
                "candidate_rank": rank,
                "candidate_segment": candidate_segment,
                "source": "segment comps",
                "scenario": "Optimistic",
                "basis": "75th percentile of full candidate segment",
                "n": len(comps),
                "nightly_price": comps["nightly_price"].quantile(0.75),
                "occupancy_rate": comps["occupancy_rate"].quantile(0.75),
                "annual_revenue": comps["annual_revenue"].quantile(0.75),
            },
        ]
    )

    revenues = comps["annual_revenue"].to_numpy()
    bootstrap_medians = []
    for _ in range(1000):
        sample = rng.choice(revenues, size=len(revenues), replace=True)
        bootstrap_medians.append(np.median(sample))
    bootstrap_medians = np.array(bootstrap_medians)

    matching_knn = knn[knn["candidate_rank"].eq(rank)]
    knn_median_revenue = np.nan
    knn_support = ""
    if not matching_knn.empty:
        knn_median_revenue = matching_knn["knn_median_revenue"].iloc[0]
        knn_support = matching_knn["validation_status"].iloc[0]

    bootstrap_rows.append(
        {
            "candidate_rank": rank,
            "candidate_segment": candidate_segment,
            "segment_comp_count": len(comps),
            "segment_median_revenue": np.median(revenues),
            "bootstrap_median_revenue_mean": bootstrap_medians.mean(),
            "bootstrap_median_revenue_ci_05": np.quantile(bootstrap_medians, 0.05),
            "bootstrap_median_revenue_ci_95": np.quantile(bootstrap_medians, 0.95),
            "bootstrap_ci_width": np.quantile(bootstrap_medians, 0.95) - np.quantile(bootstrap_medians, 0.05),
            "knn_median_revenue": knn_median_revenue,
            "knn_validation_status": knn_support,
        }
    )

    base_price = comps["nightly_price"].median()
    base_occupancy = comps["occupancy_rate"].median()
    stress_cases = [
        ("Base median", base_price, base_occupancy, "Median price and median occupancy"),
        ("Price -10%", base_price * 0.9, base_occupancy, "Pricing downside only"),
        ("Occupancy -10pp", base_price, max(base_occupancy - 0.10, 0), "Demand downside only"),
        ("Price -10% and occupancy -10pp", base_price * 0.9, max(base_occupancy - 0.10, 0), "Combined downside"),
        ("Price +10% and occupancy +5pp", base_price * 1.1, min(base_occupancy + 0.05, 1), "Upside operating case"),
    ]
    for case_name, price, occupancy, description in stress_cases:
        sensitivity_rows.append(
            {
                "candidate_rank": rank,
                "candidate_segment": candidate_segment,
                "case": case_name,
                "description": description,
                "nightly_price": price,
                "occupancy_rate": occupancy,
                "annual_revenue": price * occupancy * 365,
                "change_vs_base_revenue": (price * occupancy * 365) - (base_price * base_occupancy * 365),
            }
        )

scenario_df = pd.DataFrame(scenario_rows)
bootstrap_df = pd.DataFrame(bootstrap_rows)
sensitivity_df = pd.DataFrame(sensitivity_rows)

scenario_df.to_csv(results_dir / "step3_revenue_scenarios.csv", index=False)
bootstrap_df.to_csv(results_dir / "step3_bootstrap_revenue_uncertainty.csv", index=False)
sensitivity_df.to_csv(results_dir / "step3_sensitivity_analysis.csv", index=False)

report_path = reports_dir / "step3_bootstrap_scenarios.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Step 3: Revenue Scenarios and Bootstrap Uncertainty\n\n")
    handle.write("## Purpose\n\n")
    handle.write(
        "Step 3 estimates conservative, moderate, and optimistic annual revenue for the validated candidate segments. "
        "It also uses bootstrap resampling to quantify uncertainty around the segment median revenue.\n\n"
    )
    handle.write("## Method\n\n")
    handle.write("- Primary scenarios use the full Step 1 candidate segment, not only the 15 k-NN neighbors.\n")
    handle.write("- Conservative scenario = 25th percentile of segment comps.\n")
    handle.write("- Moderate scenario = median of segment comps.\n")
    handle.write("- Optimistic scenario = 75th percentile of segment comps.\n")
    handle.write("- Bootstrap uncertainty uses 1,000 resamples of segment annual revenue and reports a 90% interval for the median.\n")
    handle.write("- k-NN median revenue from Step 2 is included as validation, not as the primary scenario basis.\n")
    handle.write("- Sensitivity tests stress price and occupancy separately and together.\n\n")
    handle.write("## Files Created\n\n")
    handle.write("- `results/investment_decision/step3_revenue_scenarios.csv`\n")
    handle.write("- `results/investment_decision/step3_bootstrap_revenue_uncertainty.csv`\n")
    handle.write("- `results/investment_decision/step3_sensitivity_analysis.csv`\n\n")
    handle.write("## Results\n\n")
    for row in bootstrap_df.to_dict(orient="records"):
        scenarios = scenario_df[
            (scenario_df["candidate_rank"] == row["candidate_rank"])
            & (scenario_df["source"] == "segment comps")
        ]
        conservative = scenarios[scenarios["scenario"].eq("Conservative")]["annual_revenue"].iloc[0]
        moderate = scenarios[scenarios["scenario"].eq("Moderate")]["annual_revenue"].iloc[0]
        optimistic = scenarios[scenarios["scenario"].eq("Optimistic")]["annual_revenue"].iloc[0]
        handle.write(
            f"- {row['candidate_segment']}: conservative ${conservative:,.0f}, "
            f"moderate ${moderate:,.0f}, optimistic ${optimistic:,.0f}. "
            f"Bootstrap 90% interval for median revenue: "
            f"${row['bootstrap_median_revenue_ci_05']:,.0f}-${row['bootstrap_median_revenue_ci_95']:,.0f}. "
            f"k-NN median validation revenue: ${row['knn_median_revenue']:,.0f}.\n"
        )
    handle.write("\n## Interpretation\n\n")
    handle.write(
        "Quartiles describe the spread of individual listing outcomes, while the bootstrap interval describes uncertainty "
        "around the typical segment revenue estimate. The strongest candidates are those with high moderate revenue, "
        "acceptable downside revenue, a reasonably narrow bootstrap interval, and k-NN validation that agrees with or exceeds "
        "the segment estimate.\n"
    )

plot_data = scenario_df[scenario_df["scenario"].isin(["Conservative", "Moderate", "Optimistic"])].copy()
if not plot_data.empty:
    pivot = plot_data.pivot(index="candidate_segment", columns="scenario", values="annual_revenue")
    pivot = pivot[["Conservative", "Moderate", "Optimistic"]].sort_values("Moderate", ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    pivot.plot(kind="barh", ax=ax)
    ax.set_xlabel("Annual revenue")
    ax.set_title("Step 3 revenue scenarios by candidate")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, pos: f"${value/1000:.0f}K"))
    fig.tight_layout()
    fig.savefig(figures_dir / "step3_revenue_scenarios.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

print("Saved Step 3 scenario, bootstrap, and sensitivity outputs.")
print(results_dir / "step3_revenue_scenarios.csv")
print(results_dir / "step3_bootstrap_revenue_uncertainty.csv")
print(results_dir / "step3_sensitivity_analysis.csv")
print(report_path)
'''

    result = execute_python_code(code, description="Step 3 bootstrap revenue scenarios and sensitivity analysis")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
