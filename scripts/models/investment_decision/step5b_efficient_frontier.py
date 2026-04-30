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
    portfolios_path = PROJECT_ROOT / "results" / "investment_decision" / "step5_two_property_portfolio_candidates.csv"
    result = load_data(str(portfolios_path), dataset_name="portfolio_candidates")
    if result.get("status") != "success":
        raise RuntimeError(result)

    get_column_info("portfolio_candidates")
    get_summary_statistics(
        "portfolio_candidates",
        columns=["combined_moderate_revenue", "portfolio_risk_score", "combined_conservative_revenue"],
    )

    code = r'''
from pathlib import Path

project_root = Path("''' + str(PROJECT_ROOT) + r'''")
results_dir = project_root / "results" / "investment_decision"
reports_dir = project_root / "reports" / "investment_decision"
figures_dir = project_root / "reports" / "figures" / "05_investment_decision"
results_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)
figures_dir.mkdir(parents=True, exist_ok=True)

portfolios = _data_store["portfolio_candidates"].copy()
for col in [
    "combined_moderate_revenue",
    "combined_conservative_revenue",
    "combined_optimistic_revenue",
    "portfolio_risk_score",
    "portfolio_score",
    "risk_adjusted_revenue_score",
    "city_occupancy_correlation",
]:
    portfolios[col] = pd.to_numeric(portfolios[col], errors="coerce")

portfolios = portfolios.dropna(subset=["combined_moderate_revenue", "portfolio_risk_score"]).copy()

frontier_rows = []
for idx, row in portfolios.iterrows():
    dominated = portfolios[
        (portfolios["portfolio_risk_score"] <= row["portfolio_risk_score"])
        & (portfolios["combined_moderate_revenue"] >= row["combined_moderate_revenue"])
        & (
            (portfolios["portfolio_risk_score"] < row["portfolio_risk_score"])
            | (portfolios["combined_moderate_revenue"] > row["combined_moderate_revenue"])
        )
    ]
    if dominated.empty:
        frontier_rows.append(row)

frontier = pd.DataFrame(frontier_rows).sort_values(
    ["portfolio_risk_score", "combined_moderate_revenue"], ascending=[True, True]
)
frontier["frontier_rank_by_risk"] = range(1, len(frontier) + 1)
frontier.to_csv(results_dir / "step5b_efficient_frontier_portfolios.csv", index=False)

best_balanced = portfolios.sort_values("portfolio_score", ascending=False).iloc[0]
max_revenue_frontier = frontier.sort_values("combined_moderate_revenue", ascending=False).iloc[0]
lowest_risk_frontier = frontier.sort_values("portfolio_risk_score", ascending=True).iloc[0]

fig, ax = plt.subplots(figsize=(9, 6))
same_city = portfolios["same_city"].astype(str).str.lower().eq("true")
ax.scatter(
    portfolios.loc[~same_city, "portfolio_risk_score"],
    portfolios.loc[~same_city, "combined_moderate_revenue"],
    alpha=0.45,
    label="Cross-city portfolios",
    color="#2f6f73",
)
ax.scatter(
    portfolios.loc[same_city, "portfolio_risk_score"],
    portfolios.loc[same_city, "combined_moderate_revenue"],
    alpha=0.45,
    label="Same-city portfolios",
    color="#8a6f3f",
)
ax.plot(
    frontier["portfolio_risk_score"],
    frontier["combined_moderate_revenue"],
    color="#7a4e2d",
    linewidth=2.5,
    marker="o",
    label="Efficient frontier",
)
ax.scatter(
    [best_balanced["portfolio_risk_score"]],
    [best_balanced["combined_moderate_revenue"]],
    color="black",
    marker="*",
    s=180,
    label="Best balanced score",
)
ax.set_title("Step 5B: Two-Property Efficient Frontier")
ax.set_xlabel("Portfolio risk score")
ax.set_ylabel("Combined moderate annual revenue")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, pos: f"${value/1000:.0f}K"))
ax.legend()
fig.tight_layout()
fig.savefig(figures_dir / "step5b_efficient_frontier.png", dpi=150, bbox_inches="tight")
plt.close(fig)

report_path = reports_dir / "step5b_efficient_frontier.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Step 5B: Efficient Frontier Extension\n\n")
    handle.write("## Purpose\n\n")
    handle.write(
        "This extension turns the Step 5 portfolio table into a simple efficient frontier. "
        "A portfolio is on the frontier if no other portfolio has both lower or equal risk and higher or equal revenue.\n\n"
    )
    handle.write("## Assumptions and Constraints\n\n")
    handle.write("- Return is measured as combined moderate annual operating revenue.\n")
    handle.write("- Risk is the Step 5 composite portfolio risk score.\n")
    handle.write("- This is not a finance-grade mean-variance frontier because acquisition cost, expenses, and true return variance are unavailable.\n")
    handle.write("- The frontier is still useful as a decision-support visualization for revenue-risk tradeoffs.\n\n")
    handle.write("## Files Created\n\n")
    handle.write("- `results/investment_decision/step5b_efficient_frontier_portfolios.csv`\n")
    handle.write("- `reports/figures/05_investment_decision/step5b_efficient_frontier.png`\n\n")
    handle.write("## Key Frontier Options\n\n")
    handle.write(
        f"- Lowest-risk frontier portfolio: {lowest_risk_frontier['property_1']} + {lowest_risk_frontier['property_2']}. "
        f"Revenue ${lowest_risk_frontier['combined_moderate_revenue']:,.0f}, risk {lowest_risk_frontier['portfolio_risk_score']:.2f}.\n"
    )
    handle.write(
        f"- Highest-revenue frontier portfolio: {max_revenue_frontier['property_1']} + {max_revenue_frontier['property_2']}. "
        f"Revenue ${max_revenue_frontier['combined_moderate_revenue']:,.0f}, risk {max_revenue_frontier['portfolio_risk_score']:.2f}.\n"
    )
    handle.write(
        f"- Best balanced-score portfolio: {best_balanced['property_1']} + {best_balanced['property_2']}. "
        f"Revenue ${best_balanced['combined_moderate_revenue']:,.0f}, risk {best_balanced['portfolio_risk_score']:.2f}.\n\n"
    )
    handle.write("## Business Interpretation\n\n")
    handle.write(
        "The efficient frontier helps explain the tradeoff between maximizing revenue and controlling risk. "
        "The final recommendation should generally come from the frontier, because dominated portfolios give up revenue without reducing risk, "
        "or take on more risk without improving revenue.\n"
    )

print("Saved Step 5B efficient frontier outputs.")
print(results_dir / "step5b_efficient_frontier_portfolios.csv")
print(figures_dir / "step5b_efficient_frontier.png")
print(report_path)
'''

    result = execute_python_code(code, description="Step 5B efficient frontier for two-property portfolios")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
