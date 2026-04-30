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
        "segments": PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step1_decision_ready_candidate_segments.csv",
        "city_month": PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step4_calendar_city_month_metrics.csv",
        "candidate_risk": PROJECT_ROOT / "results" / "investment_decision" / "step4_candidate_risk_decomposition.csv",
        "city_risk": PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step4_city_systematic_risk.csv",
    }
    for dataset_name, path in inputs.items():
        result = load_data(str(path), dataset_name=dataset_name)
        if result.get("status") != "success":
            raise RuntimeError(f"Failed loading {path}: {result}")

    get_column_info("segments")
    get_summary_statistics(
        "segments",
        columns=["median_annual_revenue", "p25_annual_revenue", "annual_revenue_iqr", "median_occupancy_rate"],
    )

    code = r'''
from pathlib import Path
from itertools import combinations

project_root = Path("''' + str(PROJECT_ROOT) + r'''")
processed_dir = project_root / "data" / "processed" / "investment_decision"
results_dir = project_root / "results" / "investment_decision"
reports_dir = project_root / "reports" / "investment_decision"
figures_dir = project_root / "reports" / "figures"
processed_dir.mkdir(parents=True, exist_ok=True)
results_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)
figures_dir.mkdir(parents=True, exist_ok=True)

segments = _data_store["segments"].copy()
city_month = _data_store["city_month"].copy()
candidate_risk = _data_store["candidate_risk"].copy()
city_risk = _data_store["city_risk"].copy()

for frame in [segments, city_month, candidate_risk, city_risk]:
    for col in frame.columns:
        frame[col] = pd.to_numeric(frame[col], errors="ignore")

def minmax(series):
    series = pd.to_numeric(series, errors="coerce")
    low = series.min()
    high = series.max()
    if pd.isna(low) or pd.isna(high) or high == low:
        return pd.Series(0.5, index=series.index)
    return (series - low) / (high - low)

city_month["month"] = pd.to_datetime(city_month["month"], errors="coerce")
occupancy_pivot = city_month.pivot_table(
    index="month",
    columns="city",
    values="monthly_occupancy_rate",
    aggfunc="mean",
)
city_corr = occupancy_pivot.corr().fillna(0)
city_corr.to_csv(processed_dir / "step5_city_occupancy_correlation.csv")

city_risk_map = city_risk.set_index("city_key")["city_systematic_risk_score"].to_dict()
regulatory_map = {
    "new_york": 1.00,
    "san_francisco": 0.95,
    "los_angeles": 0.80,
    "hawaii": 0.70,
    "nashville": 0.45,
}

segments["candidate_segment"] = (
    segments["City"].astype(str)
    + " / "
    + segments["neighbourhood_cleansed"].astype(str)
    + " / "
    + segments["property_type"].astype(str)
    + " / "
    + segments["bedrooms"].astype(int).astype(str)
    + "BR"
)
segments["segment_downside_ratio"] = (
    (segments["median_annual_revenue"] - segments["p25_annual_revenue"]) / segments["median_annual_revenue"]
)
segments["segment_uncertainty_ratio"] = segments["annual_revenue_iqr"] / segments["median_annual_revenue"]
segments["city_systematic_risk_score"] = segments["city_key"].map(city_risk_map).fillna(0.5)
segments["regulatory_proxy_score"] = segments["city_key"].map(regulatory_map).fillna(0.5)

candidate_pool = (
    segments.sort_values(["median_annual_revenue", "risk_adjusted_revenue"], ascending=False)
    .groupby("city_key", group_keys=False)
    .head(12)
    .copy()
)
candidate_pool = candidate_pool.head(50).copy()
candidate_pool.to_csv(processed_dir / "step5_portfolio_candidate_pool.csv", index=False)

portfolio_rows = []
records = candidate_pool.to_dict(orient="records")
for left, right in combinations(records, 2):
    same_city = left["city_key"] == right["city_key"]
    same_neighborhood = (
        same_city
        and left["neighbourhood_cleansed"] == right["neighbourhood_cleansed"]
    )
    same_property_type = left["property_type"] == right["property_type"]
    city_correlation = (
        1.0
        if same_city
        else float(city_corr.loc[left["city_key"], right["city_key"]])
        if left["city_key"] in city_corr.index and right["city_key"] in city_corr.columns
        else 0.5
    )
    combined_moderate_revenue = left["median_annual_revenue"] + right["median_annual_revenue"]
    combined_conservative_revenue = left["p25_annual_revenue"] + right["p25_annual_revenue"]
    combined_optimistic_revenue = left["p75_annual_revenue"] + right["p75_annual_revenue"]
    portfolio_downside_ratio = (
        (combined_moderate_revenue - combined_conservative_revenue) / combined_moderate_revenue
    )
    avg_segment_uncertainty = np.mean([left["segment_uncertainty_ratio"], right["segment_uncertainty_ratio"]])
    avg_city_risk = np.mean([left["city_systematic_risk_score"], right["city_systematic_risk_score"]])
    avg_regulatory_risk = np.mean([left["regulatory_proxy_score"], right["regulatory_proxy_score"]])
    concentration_penalty = 0.0
    if same_city:
        concentration_penalty += 0.20
    if same_neighborhood:
        concentration_penalty += 0.20
    if same_property_type:
        concentration_penalty += 0.10
    diversification_bonus = 0.0
    if not same_city:
        diversification_bonus += 0.15
    if not same_property_type:
        diversification_bonus += 0.05
    if city_correlation < 0.5:
        diversification_bonus += 0.10

    portfolio_risk_score_raw = (
        0.25 * portfolio_downside_ratio
        + 0.20 * avg_segment_uncertainty
        + 0.20 * avg_city_risk
        + 0.15 * avg_regulatory_risk
        + 0.10 * max(city_correlation, 0)
        + concentration_penalty
        - diversification_bonus
    )
    portfolio_rows.append(
        {
            "property_1": left["candidate_segment"],
            "property_2": right["candidate_segment"],
            "property_1_city": left["City"],
            "property_2_city": right["City"],
            "property_1_type": left["property_type"],
            "property_2_type": right["property_type"],
            "same_city": same_city,
            "same_neighborhood": same_neighborhood,
            "same_property_type": same_property_type,
            "city_occupancy_correlation": city_correlation,
            "combined_conservative_revenue": combined_conservative_revenue,
            "combined_moderate_revenue": combined_moderate_revenue,
            "combined_optimistic_revenue": combined_optimistic_revenue,
            "portfolio_downside_ratio": portfolio_downside_ratio,
            "avg_segment_uncertainty": avg_segment_uncertainty,
            "avg_city_systematic_risk": avg_city_risk,
            "avg_regulatory_risk": avg_regulatory_risk,
            "concentration_penalty": concentration_penalty,
            "diversification_bonus": diversification_bonus,
            "portfolio_risk_score_raw": portfolio_risk_score_raw,
        }
    )

portfolios = pd.DataFrame(portfolio_rows)
portfolios["portfolio_risk_score"] = minmax(portfolios["portfolio_risk_score_raw"])
portfolios["portfolio_return_score"] = minmax(portfolios["combined_moderate_revenue"])
portfolios["portfolio_score"] = (
    0.65 * portfolios["portfolio_return_score"]
    - 0.35 * portfolios["portfolio_risk_score"]
    + 0.10 * portfolios["diversification_bonus"]
)
portfolios["risk_adjusted_revenue_score"] = (
    portfolios["combined_moderate_revenue"] / (1 + portfolios["portfolio_risk_score"])
)

portfolios = portfolios.sort_values("portfolio_score", ascending=False)
portfolios.to_csv(results_dir / "step5_two_property_portfolio_candidates.csv", index=False)

max_revenue = portfolios.sort_values("combined_moderate_revenue", ascending=False).iloc[0].copy()
diversified = portfolios[
    (~portfolios["same_city"]) & (portfolios["city_occupancy_correlation"] < 0.75)
].sort_values("portfolio_score", ascending=False).iloc[0].copy()
lower_risk = portfolios.sort_values(["portfolio_risk_score", "combined_moderate_revenue"], ascending=[True, False]).iloc[0].copy()

recommended = pd.DataFrame(
    [
        {"portfolio_type": "Max revenue", **max_revenue.to_dict()},
        {"portfolio_type": "Diversified", **diversified.to_dict()},
        {"portfolio_type": "Lower risk", **lower_risk.to_dict()},
    ]
)
recommended.to_csv(results_dir / "step5_recommended_portfolios.csv", index=False)

report_path = reports_dir / "step5_portfolio_diversification.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Step 5: Two-Property Portfolio Diversification\n\n")
    handle.write("## Purpose\n\n")
    handle.write(
        "Step 5 answers whether the client should allocate a two-property investment across markets or property types. "
        "The goal is not only to maximize revenue, but also to reduce concentration, seasonality, and systematic market risk.\n\n"
    )
    handle.write("## Assumptions and Constraints\n\n")
    handle.write("- Each portfolio contains two budget-feasible candidate segments from Step 1.\n")
    handle.write("- This is still operating-revenue analysis, not ROI, because acquisition prices and expenses are unavailable.\n")
    handle.write("- City monthly occupancy correlations are used as a diversification proxy.\n")
    handle.write("- Regulatory risk remains a proxy and requires external legal due diligence.\n\n")
    handle.write("## Method\n\n")
    handle.write("- Built a candidate pool from the strongest decision-ready segments in each city.\n")
    handle.write("- Generated all two-property combinations from that pool.\n")
    handle.write("- Computed combined conservative, moderate, and optimistic revenue.\n")
    handle.write("- Penalized same-city, same-neighborhood, same-property-type, high-correlation, and high-risk pairs.\n")
    handle.write("- Reported three options: max revenue, diversified, and lower risk.\n\n")
    handle.write("## Files Created\n\n")
    handle.write("- `data/processed/investment_decision/step5_portfolio_candidate_pool.csv`\n")
    handle.write("- `data/processed/investment_decision/step5_city_occupancy_correlation.csv`\n")
    handle.write("- `results/investment_decision/step5_two_property_portfolio_candidates.csv`\n")
    handle.write("- `results/investment_decision/step5_recommended_portfolios.csv`\n\n")
    handle.write("## Recommended Portfolio Options\n\n")
    for row in recommended.to_dict(orient="records"):
        handle.write(
            f"- {row['portfolio_type']}: {row['property_1']} + {row['property_2']}. "
            f"Moderate combined revenue ${row['combined_moderate_revenue']:,.0f}; "
            f"conservative ${row['combined_conservative_revenue']:,.0f}; "
            f"optimistic ${row['combined_optimistic_revenue']:,.0f}; "
            f"risk score {row['portfolio_risk_score']:.2f}; "
            f"city occupancy correlation {row['city_occupancy_correlation']:.2f}.\n"
        )
    handle.write("\n## Business Interpretation\n\n")
    handle.write(
        "The max-revenue option may concentrate exposure in one market or property type. The diversified option is usually more appropriate "
        "for a risk-aware client because it balances revenue with lower correlation across city demand cycles. A frontier-style extension is possible "
        "from these portfolio candidates by plotting combined revenue against portfolio risk and identifying efficient pairs.\n"
    )

plot = portfolios.head(60).copy()
fig, ax = plt.subplots(figsize=(9, 6))
colors = np.where(plot["same_city"], "#7a4e2d", "#2f6f73")
ax.scatter(plot["portfolio_risk_score"], plot["combined_moderate_revenue"], c=colors, alpha=0.75)
ax.set_xlabel("Portfolio risk score")
ax.set_ylabel("Combined moderate annual revenue")
ax.set_title("Step 5: Portfolio Revenue vs Risk")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, pos: f"${value/1000:.0f}K"))
fig.tight_layout()
fig.savefig(figures_dir / "step5_portfolio_revenue_vs_risk.png", dpi=150, bbox_inches="tight")
plt.close(fig)

rec_plot = recommended.sort_values("combined_moderate_revenue", ascending=True)
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.barh(rec_plot["portfolio_type"], rec_plot["combined_moderate_revenue"], color="#5d5b8a")
ax.set_xlabel("Combined moderate annual revenue")
ax.set_title("Step 5: Recommended Portfolio Options")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, pos: f"${value/1000:.0f}K"))
fig.tight_layout()
fig.savefig(figures_dir / "step5_recommended_portfolios.png", dpi=150, bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(6.5, 5.5))
im = ax.imshow(city_corr.values, cmap="RdYlGn", vmin=-1, vmax=1)
ax.set_xticks(np.arange(len(city_corr.columns)))
ax.set_xticklabels(city_corr.columns, rotation=35, ha="right")
ax.set_yticks(np.arange(len(city_corr.index)))
ax.set_yticklabels(city_corr.index)
ax.set_title("Step 5: City Occupancy Correlation")
fig.colorbar(im, ax=ax, label="Correlation")
fig.tight_layout()
fig.savefig(figures_dir / "step5_city_occupancy_correlation.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print("Saved Step 5 portfolio diversification outputs.")
print(results_dir / "step5_two_property_portfolio_candidates.csv")
print(results_dir / "step5_recommended_portfolios.csv")
print(report_path)
'''

    result = execute_python_code(code, description="Step 5 two-property portfolio diversification")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
