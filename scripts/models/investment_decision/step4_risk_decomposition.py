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
    inputs = {
        "listing_metrics": PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step1_budget_feasible_listing_metrics.csv",
        "decision_segments": PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step1_decision_ready_candidate_segments.csv",
        "month_metrics": PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step1_calendar_city_month_metrics.csv",
        "top_segments": PROJECT_ROOT / "results" / "investment_decision" / "step1_top_candidate_segments.csv",
        "scenarios": PROJECT_ROOT / "results" / "investment_decision" / "step3_revenue_scenarios.csv",
        "bootstrap": PROJECT_ROOT / "results" / "investment_decision" / "step3_bootstrap_revenue_uncertainty.csv",
    }
    for dataset_name, path in inputs.items():
        result = load_data(str(path), dataset_name=dataset_name)
        if result.get("status") != "success":
            raise RuntimeError(f"Failed loading {path}: {result}")

    get_column_info("listing_metrics")
    get_summary_statistics(
        "listing_metrics",
        columns=["annual_revenue", "occupancy_rate", "nightly_price", "review_scores_rating"],
    )

    code = r'''
from pathlib import Path

project_root = Path("''' + str(PROJECT_ROOT) + r'''")
processed_dir = project_root / "data" / "processed" / "investment_decision"
results_dir = project_root / "results" / "investment_decision"
reports_dir = project_root / "reports" / "investment_decision"
figures_dir = project_root / "reports" / "figures" / "05_investment_decision"
processed_dir.mkdir(parents=True, exist_ok=True)
results_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)
figures_dir.mkdir(parents=True, exist_ok=True)

listings = _data_store["listing_metrics"].copy()
segments_all = _data_store["decision_segments"].copy()
months = _data_store["month_metrics"].copy()
top_segments = _data_store["top_segments"].copy().head(5)
scenarios = _data_store["scenarios"].copy()
bootstrap = _data_store["bootstrap"].copy()

numeric_columns = [
    "annual_revenue",
    "occupancy_rate",
    "nightly_price",
    "review_scores_rating",
    "bedroom_count",
    "calendar_days",
    "booked_days",
    "available_days",
    "monthly_occupancy_rate",
    "comp_count",
    "median_annual_revenue",
    "p25_annual_revenue",
    "p75_annual_revenue",
    "downside_gap",
    "annual_revenue_iqr",
    "bootstrap_ci_width",
    "segment_median_revenue",
]
for frame in [listings, segments_all, months, top_segments, scenarios, bootstrap]:
    for col in numeric_columns:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

def minmax(series):
    series = pd.to_numeric(series, errors="coerce")
    low = series.min()
    high = series.max()
    if pd.isna(low) or pd.isna(high) or high == low:
        return pd.Series(0.5, index=series.index)
    return (series - low) / (high - low)

city_systematic = months.groupby("city", dropna=False).agg(
    city_avg_monthly_occupancy=("monthly_occupancy_rate", "mean"),
    city_min_monthly_occupancy=("monthly_occupancy_rate", "min"),
    city_max_monthly_occupancy=("monthly_occupancy_rate", "max"),
    city_std_monthly_occupancy=("monthly_occupancy_rate", "std"),
    city_total_calendar_days=("calendar_days", "sum"),
).reset_index()
city_systematic["city_seasonality_gap"] = (
    city_systematic["city_max_monthly_occupancy"] - city_systematic["city_min_monthly_occupancy"]
)
city_systematic["city_seasonality_cv"] = (
    city_systematic["city_std_monthly_occupancy"] / city_systematic["city_avg_monthly_occupancy"]
)

city_supply = listings.groupby(["city_key", "City"], dropna=False).agg(
    city_budget_feasible_listings=("id", "nunique"),
    city_median_occupancy=("occupancy_rate", "median"),
    city_median_annual_revenue=("annual_revenue", "median"),
).reset_index()
city_systematic = city_systematic.merge(
    city_supply,
    left_on="city",
    right_on="city_key",
    how="left",
)
city_systematic["city_competition_score"] = minmax(np.log1p(city_systematic["city_budget_feasible_listings"]))
city_systematic["city_seasonality_score"] = minmax(city_systematic["city_seasonality_gap"])
city_systematic["city_systematic_risk_score"] = (
    0.55 * city_systematic["city_competition_score"]
    + 0.45 * city_systematic["city_seasonality_score"]
)
city_systematic.to_csv(processed_dir / "step4_city_systematic_risk.csv", index=False)

neighborhood_systematic = listings.groupby(
    ["city_key", "City", "neighbourhood_cleansed", "neighbourhood_group_cleansed"], dropna=False
).agg(
    neighborhood_budget_feasible_listings=("id", "nunique"),
    neighborhood_median_occupancy=("occupancy_rate", "median"),
    neighborhood_median_annual_revenue=("annual_revenue", "median"),
    neighborhood_p25_annual_revenue=("annual_revenue", lambda s: s.quantile(0.25)),
).reset_index()
neighborhood_systematic["neighborhood_downside_gap"] = (
    neighborhood_systematic["neighborhood_median_annual_revenue"]
    - neighborhood_systematic["neighborhood_p25_annual_revenue"]
)
neighborhood_systematic.to_csv(processed_dir / "step4_neighborhood_systematic_risk.csv", index=False)

regulatory_scores = {
    "new_york": 1.00,
    "san_francisco": 0.95,
    "los_angeles": 0.80,
    "hawaii": 0.70,
    "nashville": 0.45,
}
regulatory_notes = {
    "new_york": "High proxy: NYC short-term-rental regulation is a major due-diligence item.",
    "san_francisco": "High proxy: San Francisco short-term-rental regulation is a major due-diligence item.",
    "los_angeles": "Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.",
    "hawaii": "Elevated proxy: Hawaii rules vary strongly by island/county and resort zoning.",
    "nashville": "Moderate proxy: Nashville still requires permit and zoning due diligence.",
}

candidate_rows = []
for rank, segment in enumerate(top_segments.to_dict(orient="records"), start=1):
    city_key = segment["city_key"]
    candidate_segment = (
        f"{segment['City']} / {segment['neighbourhood_cleansed']} / "
        f"{segment['property_type']} / {int(segment['bedroom_count'])}BR"
    )
    scenario_rows = scenarios[scenarios["candidate_rank"].eq(rank)]
    conservative = scenario_rows[scenario_rows["scenario"].eq("Conservative")]["annual_revenue"].iloc[0]
    moderate = scenario_rows[scenario_rows["scenario"].eq("Moderate")]["annual_revenue"].iloc[0]
    downside_gap = moderate - conservative
    downside_ratio = downside_gap / moderate if moderate else np.nan

    boot = bootstrap[bootstrap["candidate_rank"].eq(rank)].iloc[0]
    bootstrap_uncertainty_ratio = boot["bootstrap_ci_width"] / boot["segment_median_revenue"]

    city_row = city_systematic[city_systematic["city"].eq(city_key)].iloc[0]
    neighborhood_row = neighborhood_systematic[
        neighborhood_systematic["city_key"].eq(city_key)
        & neighborhood_systematic["neighbourhood_cleansed"].eq(segment["neighbourhood_cleansed"])
    ].iloc[0]

    candidate_rows.append(
        {
            "candidate_rank": rank,
            "candidate_segment": candidate_segment,
            "city_key": city_key,
            "City": segment["City"],
            "neighbourhood_cleansed": segment["neighbourhood_cleansed"],
            "property_type": segment["property_type"],
            "bedrooms": int(segment["bedroom_count"]),
            "moderate_revenue": moderate,
            "conservative_revenue": conservative,
            "downside_gap": downside_gap,
            "downside_ratio": downside_ratio,
            "bootstrap_ci_width": boot["bootstrap_ci_width"],
            "bootstrap_uncertainty_ratio": bootstrap_uncertainty_ratio,
            "city_seasonality_gap": city_row["city_seasonality_gap"],
            "city_seasonality_cv": city_row["city_seasonality_cv"],
            "segment_comp_count": segment["comp_count"],
            "neighborhood_budget_feasible_listings": neighborhood_row["neighborhood_budget_feasible_listings"],
            "neighborhood_median_occupancy": neighborhood_row["neighborhood_median_occupancy"],
            "city_budget_feasible_listings": city_row["city_budget_feasible_listings"],
            "regulatory_proxy_score": regulatory_scores.get(city_key, 0.5),
            "regulatory_proxy_note": regulatory_notes.get(city_key, "Proxy not classified; requires external due diligence."),
        }
    )

risk = pd.DataFrame(candidate_rows)
risk["downside_risk_score"] = minmax(risk["downside_ratio"])
risk["uncertainty_risk_score"] = minmax(risk["bootstrap_uncertainty_ratio"])
risk["seasonality_risk_score"] = minmax(risk["city_seasonality_gap"])
risk["competition_risk_score"] = minmax(np.log1p(risk["neighborhood_budget_feasible_listings"]))
risk["regulatory_risk_score"] = risk["regulatory_proxy_score"]
risk["overall_risk_score"] = (
    0.25 * risk["downside_risk_score"]
    + 0.25 * risk["uncertainty_risk_score"]
    + 0.20 * risk["seasonality_risk_score"]
    + 0.15 * risk["competition_risk_score"]
    + 0.15 * risk["regulatory_risk_score"]
)
risk["risk_adjusted_revenue_score"] = (
    risk["moderate_revenue"] / (1 + risk["overall_risk_score"])
)
risk = risk.sort_values("overall_risk_score", ascending=True)
risk.to_csv(results_dir / "step4_candidate_risk_decomposition.csv", index=False)

risk_rankings = risk.sort_values("risk_adjusted_revenue_score", ascending=False).copy()
risk_rankings.to_csv(results_dir / "step4_risk_adjusted_rankings.csv", index=False)

report_path = reports_dir / "step4_risk_decomposition.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Step 4: Risk Decomposition\n\n")
    handle.write("## Purpose\n\n")
    handle.write(
        "Step 4 evaluates the top investment candidates by downside revenue risk, bootstrap uncertainty, "
        "seasonality, competition, and regulatory proxy risk. It also preserves full city and neighborhood systematic-risk tables.\n\n"
    )
    handle.write("## Risk Components\n\n")
    handle.write("- Downside revenue risk: how far conservative revenue falls below moderate revenue.\n")
    handle.write("- Bootstrap uncertainty risk: width of the bootstrap median-revenue interval relative to median revenue.\n")
    handle.write("- Seasonality risk: city-level peak-to-trough monthly occupancy gap from calendar data.\n")
    handle.write("- Competitive risk: budget-feasible listing count in the candidate neighborhood.\n")
    handle.write("- Regulatory proxy risk: city-level qualitative score based on known need for short-term-rental due diligence.\n\n")
    handle.write("## Files Created\n\n")
    handle.write("- `data/processed/investment_decision/step4_city_systematic_risk.csv`\n")
    handle.write("- `data/processed/investment_decision/step4_neighborhood_systematic_risk.csv`\n")
    handle.write("- `results/investment_decision/step4_candidate_risk_decomposition.csv`\n")
    handle.write("- `results/investment_decision/step4_risk_adjusted_rankings.csv`\n\n")
    handle.write("## Candidate Risk Results\n\n")
    for row in risk_rankings.to_dict(orient="records"):
        handle.write(
            f"- {row['candidate_segment']}: moderate revenue ${row['moderate_revenue']:,.0f}, "
            f"overall risk score {row['overall_risk_score']:.2f}, "
            f"risk-adjusted revenue score ${row['risk_adjusted_revenue_score']:,.0f}. "
            f"Main regulatory note: {row['regulatory_proxy_note']}\n"
        )
    handle.write("\n## Interpretation\n\n")
    handle.write(
        "This step does not eliminate high-revenue candidates automatically. Instead, it clarifies the tradeoff: "
        "a candidate can have superior revenue but also higher uncertainty, seasonality, competition, or regulatory exposure. "
        "The final recommendation should consider both moderate revenue and risk-adjusted ranking.\n"
    )

plot_risk = risk.sort_values("overall_risk_score", ascending=True)
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(plot_risk["candidate_segment"], plot_risk["overall_risk_score"], color="#7a4e2d")
ax.set_xlabel("Overall risk score")
ax.set_title("Step 4: Overall Risk by Candidate")
fig.tight_layout()
fig.savefig(figures_dir / "step4_risk_score_by_candidate.png", dpi=150, bbox_inches="tight")
plt.close(fig)

components = risk_rankings[
    [
        "candidate_segment",
        "downside_risk_score",
        "uncertainty_risk_score",
        "seasonality_risk_score",
        "competition_risk_score",
        "regulatory_risk_score",
    ]
].set_index("candidate_segment")
fig, ax = plt.subplots(figsize=(10, 5.5))
im = ax.imshow(components.values, aspect="auto", cmap="YlOrRd")
ax.set_xticks(np.arange(len(components.columns)))
ax.set_xticklabels(
    ["Downside", "Uncertainty", "Seasonality", "Competition", "Regulatory"],
    rotation=35,
    ha="right",
)
ax.set_yticks(np.arange(len(components.index)))
ax.set_yticklabels(components.index)
ax.set_title("Step 4: Risk Component Heatmap")
fig.colorbar(im, ax=ax, label="Risk score")
fig.tight_layout()
fig.savefig(figures_dir / "step4_risk_components_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)

city_plot = city_systematic.sort_values("city_seasonality_gap", ascending=True)
fig, ax = plt.subplots(figsize=(8, 4.8))
ax.barh(city_plot["City"], city_plot["city_seasonality_gap"], color="#2f6f73")
ax.set_xlabel("Peak-to-trough monthly occupancy gap")
ax.set_title("Step 4: City Seasonality Risk")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, pos: f"{value:.0%}"))
fig.tight_layout()
fig.savefig(figures_dir / "step4_city_seasonality.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print("Saved Step 4 risk decomposition outputs.")
print(results_dir / "step4_candidate_risk_decomposition.csv")
print(results_dir / "step4_risk_adjusted_rankings.csv")
print(report_path)
'''

    result = execute_python_code(code, description="Step 4 risk decomposition for investment candidates")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
