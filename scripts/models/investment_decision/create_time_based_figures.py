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
    month_metrics = PROJECT_ROOT / "data" / "processed" / "investment_decision" / "step4_calendar_city_month_metrics.csv"
    result = load_data(str(month_metrics), dataset_name="city_month_metrics")
    if result.get("status") != "success":
        raise RuntimeError(result)

    code = r'''
from pathlib import Path

project_root = Path("''' + str(PROJECT_ROOT) + r'''")
figures_dir = project_root / "reports" / "figures"
reports_dir = project_root / "reports" / "investment_decision"
figures_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)

monthly = _data_store["city_month_metrics"].copy()
monthly["month"] = pd.to_datetime(monthly["month"], errors="coerce")
monthly["monthly_occupancy_rate"] = pd.to_numeric(monthly["monthly_occupancy_rate"], errors="coerce")
monthly = monthly.dropna(subset=["month", "monthly_occupancy_rate"]).sort_values(["city", "month"])

city_label_map = {
    "hawaii": "Hawaii",
    "los_angeles": "Los Angeles",
    "nashville": "Nashville",
    "new_york": "New York",
    "san_francisco": "San Francisco",
}
monthly["city_label"] = monthly["city"].map(city_label_map).fillna(monthly["city"])

fig, ax = plt.subplots(figsize=(10, 5.5))
for city, city_df in monthly.groupby("city_label"):
    ax.plot(city_df["month"], city_df["monthly_occupancy_rate"], marker="o", linewidth=2, label=city)
ax.set_title("Monthly Occupancy by City")
ax.set_xlabel("Month")
ax.set_ylabel("Occupancy rate")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, pos: f"{value:.0%}"))
ax.legend(ncol=2, fontsize=9)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(figures_dir / "step4_monthly_occupancy_by_city.png", dpi=150, bbox_inches="tight")
plt.close(fig)

indexed = monthly.copy()
indexed["city_avg_occupancy"] = indexed.groupby("city")["monthly_occupancy_rate"].transform("mean")
indexed["occupancy_index"] = indexed["monthly_occupancy_rate"] / indexed["city_avg_occupancy"]

fig, ax = plt.subplots(figsize=(10, 5.5))
for city, city_df in indexed.groupby("city_label"):
    ax.plot(city_df["month"], city_df["occupancy_index"], marker="o", linewidth=2, label=city)
ax.axhline(1.0, color="black", linewidth=1, linestyle="--")
ax.set_title("Monthly Occupancy Index by City")
ax.set_xlabel("Month")
ax.set_ylabel("Index vs city average")
ax.legend(ncol=2, fontsize=9)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(figures_dir / "step4_monthly_occupancy_index_by_city.png", dpi=150, bbox_inches="tight")
plt.close(fig)

seasonality = monthly.groupby("city_label").agg(
    avg_occupancy=("monthly_occupancy_rate", "mean"),
    min_occupancy=("monthly_occupancy_rate", "min"),
    max_occupancy=("monthly_occupancy_rate", "max"),
    std_occupancy=("monthly_occupancy_rate", "std"),
).reset_index()
seasonality["peak_to_trough_gap"] = seasonality["max_occupancy"] - seasonality["min_occupancy"]
seasonality["coefficient_of_variation"] = seasonality["std_occupancy"] / seasonality["avg_occupancy"]
seasonality = seasonality.sort_values("peak_to_trough_gap", ascending=False)

report_path = reports_dir / "time_based_figures.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Time-Based Calendar Figures\n\n")
    handle.write("## Data Used\n\n")
    handle.write("- Monthly occupancy comes from `data/processed/calendars/calendar_all_cleaned.csv` through `data/processed/investment_decision/step4_calendar_city_month_metrics.csv`.\n")
    handle.write("- This keeps time-based risk separate from `master_data.csv`, which is listing-level and annualized.\n\n")
    handle.write("## Figures Created\n\n")
    handle.write("- `reports/figures/step4_monthly_occupancy_by_city.png`: monthly occupancy rate for each city.\n")
    handle.write("- `reports/figures/step4_monthly_occupancy_index_by_city.png`: each city's monthly occupancy indexed to its own average.\n\n")
    handle.write("## Seasonality Summary\n\n")
    for row in seasonality.to_dict(orient="records"):
        handle.write(
            f"- {row['city_label']}: average occupancy {row['avg_occupancy']:.1%}, "
            f"peak-to-trough gap {row['peak_to_trough_gap']:.1%}, "
            f"coefficient of variation {row['coefficient_of_variation']:.2f}.\n"
        )
    handle.write("\n## Interpretation\n\n")
    handle.write(
        "These time-based graphs support the risk section by showing whether revenue exposure is stable year-round "
        "or concentrated in high-demand months. The indexed chart is useful because it compares each city against its own baseline, "
        "making seasonal swings easier to compare across markets with different average occupancy levels.\n"
    )

print("Saved time-based investment decision figures.")
print(figures_dir / "step4_monthly_occupancy_by_city.png")
print(figures_dir / "step4_monthly_occupancy_index_by_city.png")
print(report_path)
'''

    result = execute_python_code(code, description="Create time-based monthly occupancy figures")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
