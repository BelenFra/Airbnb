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

from mba706_toolkit import execute_python_code, load_data


def main() -> None:
    paths = {
        "step1_segments": PROJECT_ROOT / "results" / "investment_decision" / "step1_top_candidate_segments.csv",
        "step1_city": PROJECT_ROOT / "results" / "investment_decision" / "step1_city_candidate_summary.csv",
        "step2_knn": PROJECT_ROOT / "results" / "investment_decision" / "step2_knn_candidate_validation_summary.csv",
        "step3_scenarios": PROJECT_ROOT / "results" / "investment_decision" / "step3_revenue_scenarios.csv",
        "step3_bootstrap": PROJECT_ROOT / "results" / "investment_decision" / "step3_bootstrap_revenue_uncertainty.csv",
        "step3_sensitivity": PROJECT_ROOT / "results" / "investment_decision" / "step3_sensitivity_analysis.csv",
    }
    for name, path in paths.items():
        result = load_data(str(path), dataset_name=name)
        if result.get("status") != "success":
            raise RuntimeError(f"Could not load {path}: {result}")

    code = r'''
from pathlib import Path

project_root = Path("''' + str(PROJECT_ROOT) + r'''")
figures_dir = project_root / "reports" / "figures"
reports_dir = project_root / "reports" / "investment_decision"
figures_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)

step1_segments = _data_store["step1_segments"].copy()
step1_city = _data_store["step1_city"].copy()
step2_knn = _data_store["step2_knn"].copy()
step3_scenarios = _data_store["step3_scenarios"].copy()
step3_bootstrap = _data_store["step3_bootstrap"].copy()
step3_sensitivity = _data_store["step3_sensitivity"].copy()

for frame in [step1_segments, step1_city, step2_knn, step3_scenarios, step3_bootstrap, step3_sensitivity]:
    for col in frame.columns:
        frame[col] = pd.to_numeric(frame[col], errors="ignore")

def money_axis(ax):
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, pos: f"${value/1000:.0f}K"))

def save_barh(data, labels, values, filename, title, xlabel, color="#2f6f73"):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels, values, color=color)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    money_axis(ax)
    fig.tight_layout()
    fig.savefig(figures_dir / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)

top10 = step1_segments.head(10).copy()
top10["label"] = (
    top10["City"].astype(str)
    + " / "
    + top10["neighbourhood_cleansed"].astype(str)
    + " / "
    + top10["property_type"].astype(str)
    + " / "
    + top10["bedrooms"].astype(int).astype(str)
    + "BR"
)
plot_top10 = top10.sort_values("median_annual_revenue", ascending=True)
save_barh(
    plot_top10,
    plot_top10["label"],
    plot_top10["median_annual_revenue"],
    "step1_top_candidate_revenue.png",
    "Step 1: Top Budget-Feasible Candidate Segments",
    "Median annual revenue",
)

plot_city = step1_city.sort_values("best_segment_revenue", ascending=True)
save_barh(
    plot_city,
    plot_city["City"],
    plot_city["best_segment_revenue"],
    "step1_best_segment_by_city.png",
    "Step 1: Best Candidate Segment Revenue by City",
    "Best segment median annual revenue",
    color="#5d5b8a",
)

knn_plot = step2_knn.sort_values("candidate_segment_median_revenue", ascending=True).copy()
fig, ax = plt.subplots(figsize=(10, 6))
y = np.arange(len(knn_plot))
ax.barh(y - 0.18, knn_plot["candidate_segment_median_revenue"], height=0.36, label="Segment median", color="#8a6f3f")
ax.barh(y + 0.18, knn_plot["knn_median_revenue"], height=0.36, label="k-NN median", color="#2f6f73")
ax.set_yticks(y)
ax.set_yticklabels(knn_plot["candidate_segment"])
ax.set_title("Step 2: Segment Median vs k-NN Comparable Median")
ax.set_xlabel("Annual revenue")
money_axis(ax)
ax.legend()
fig.tight_layout()
fig.savefig(figures_dir / "step2_knn_validation_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)

scenario_plot = step3_scenarios.pivot(index="candidate_segment", columns="scenario", values="annual_revenue")
scenario_plot = scenario_plot[["Conservative", "Moderate", "Optimistic"]].sort_values("Moderate", ascending=True)
fig, ax = plt.subplots(figsize=(10, 6))
scenario_plot.plot(kind="barh", ax=ax, color=["#8a6f3f", "#2f6f73", "#5d5b8a"])
ax.set_title("Step 3: Revenue Scenarios")
ax.set_xlabel("Annual revenue")
money_axis(ax)
fig.tight_layout()
fig.savefig(figures_dir / "step3_revenue_scenarios.png", dpi=150, bbox_inches="tight")
plt.close(fig)

boot = step3_bootstrap.sort_values("segment_median_revenue", ascending=True).copy()
fig, ax = plt.subplots(figsize=(10, 6))
xerr = [
    boot["segment_median_revenue"] - boot["bootstrap_median_revenue_ci_05"],
    boot["bootstrap_median_revenue_ci_95"] - boot["segment_median_revenue"],
]
ax.errorbar(
    boot["segment_median_revenue"],
    boot["candidate_segment"],
    xerr=xerr,
    fmt="o",
    color="#2f6f73",
    ecolor="#7a4e2d",
    capsize=4,
)
ax.set_title("Step 3: Bootstrap 90% Interval for Median Revenue")
ax.set_xlabel("Median annual revenue")
money_axis(ax)
fig.tight_layout()
fig.savefig(figures_dir / "step3_bootstrap_median_uncertainty.png", dpi=150, bbox_inches="tight")
plt.close(fig)

sensitivity = step3_sensitivity[step3_sensitivity["candidate_rank"].eq(1)].copy()
sensitivity = sensitivity.sort_values("annual_revenue", ascending=True)
save_barh(
    sensitivity,
    sensitivity["case"],
    sensitivity["annual_revenue"],
    "step3_top_candidate_sensitivity.png",
    "Step 3: Sensitivity for Top Candidate",
    "Annual revenue",
    color="#7a4e2d",
)

report_path = reports_dir / "figures_index.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Investment Decision Figures Index\n\n")
    handle.write("These figures support Steps 1-3 of the investment decision analysis.\n\n")
    handle.write("- `reports/figures/step1_top_candidate_revenue.png`: ranks the top budget-feasible segments by median annual revenue.\n")
    handle.write("- `reports/figures/step1_best_segment_by_city.png`: compares each city's strongest feasible segment.\n")
    handle.write("- `reports/figures/step2_knn_validation_comparison.png`: compares segment medians with k-NN comparable-listing medians.\n")
    handle.write("- `reports/figures/step3_revenue_scenarios.png`: shows conservative, moderate, and optimistic revenue cases.\n")
    handle.write("- `reports/figures/step3_bootstrap_median_uncertainty.png`: shows bootstrap uncertainty around median revenue.\n")
    handle.write("- `reports/figures/step3_top_candidate_sensitivity.png`: stress-tests the current top candidate.\n")

print("Saved investment decision figures.")
print(report_path)
'''

    result = execute_python_code(code, description="Create figures for investment decision Steps 1-3")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
