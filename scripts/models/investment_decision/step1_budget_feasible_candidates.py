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
    master_path = PROJECT_ROOT / "data" / "processed" / "master_data.csv"

    load_result = load_data(str(master_path), dataset_name="master_data")
    if load_result.get("status") != "success":
        raise RuntimeError(load_result)

    get_column_info("master_data")
    get_summary_statistics(
        "master_data",
        columns=[
            "price",
            "estimated_occupancy_l365d",
            "estimated_revenue_l365d",
            "occupancy_rate_proxy",
            "review_scores_rating",
            "reviews_per_month",
            "number_of_reviews",
        ],
    )

    code = r'''
from pathlib import Path
import numpy as np
import pandas as pd

project_root = Path("''' + str(PROJECT_ROOT) + r'''")
processed_dir = project_root / "data" / "processed" / "investment_decision"
results_dir = project_root / "results" / "investment_decision"
reports_dir = project_root / "reports" / "investment_decision"
processed_dir.mkdir(parents=True, exist_ok=True)
results_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)

calendar_metrics_path = processed_dir / "step1_calendar_listing_metrics.csv"

df = _data_store["master_data"].copy()
df.columns = [str(col).lstrip("\ufeff") for col in df.columns]

required_columns = [
    "id",
    "City",
    "neighbourhood_cleansed",
    "neighbourhood_group_cleansed",
    "room_type",
    "property_type",
    "bedrooms",
    "bathrooms",
    "beds",
    "price",
    "review_scores_rating",
    "reviews_per_month",
    "number_of_reviews",
    "estimated_occupancy_l365d",
    "estimated_revenue_l365d",
    "availability_365",
    "occupancy_rate_proxy",
]
missing_columns = [col for col in required_columns if col not in df.columns]
if missing_columns:
    raise ValueError(f"Missing required columns: {missing_columns}")

numeric_cols = [
    "id",
    "bedrooms",
    "bathrooms",
    "beds",
    "price",
    "review_scores_rating",
    "reviews_per_month",
    "number_of_reviews",
    "estimated_occupancy_l365d",
    "estimated_revenue_l365d",
    "availability_365",
    "occupancy_rate_proxy",
]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["listing_id"] = df["id"]
df["city_key"] = df["City"].astype(str).str.strip().str.lower().str.replace(" ", "_", regex=False)
df["neighbourhood_group_cleansed"] = df["neighbourhood_group_cleansed"].fillna("unknown")
df["property_type_clean"] = df["property_type"].astype(str).str.lower()
df["bedroom_count"] = df["bedrooms"].round()
df["calendar_days"] = 365
df["booked_days"] = df["estimated_occupancy_l365d"].clip(lower=0, upper=365)
df["available_days"] = df["availability_365"].clip(lower=0, upper=365)
df["calendar_occupancy_rate"] = df["occupancy_rate_proxy"].clip(lower=0, upper=1)
df.loc[df["calendar_occupancy_rate"].isna(), "calendar_occupancy_rate"] = (
    df.loc[df["calendar_occupancy_rate"].isna(), "booked_days"] / 365
)
df["avg_calendar_rate"] = np.where(
    df["booked_days"].gt(0) & df["estimated_revenue_l365d"].gt(0),
    df["estimated_revenue_l365d"] / df["booked_days"],
    df["price"],
)
df["median_calendar_rate"] = df["avg_calendar_rate"]
df["available_priced_days"] = df["booked_days"].where(df["estimated_revenue_l365d"].gt(0), np.nan)

calendar_listing_metrics = df[
    [
        "city_key",
        "listing_id",
        "calendar_days",
        "booked_days",
        "available_days",
        "available_priced_days",
        "avg_calendar_rate",
        "median_calendar_rate",
        "calendar_occupancy_rate",
    ]
].rename(columns={"city_key": "city"})
calendar_listing_metrics.to_csv(calendar_metrics_path, index=False)

analysis = df.copy()
analysis["nightly_price"] = analysis["median_calendar_rate"].fillna(analysis["price"])
analysis["occupancy_rate"] = analysis["calendar_occupancy_rate"]
analysis["annual_revenue"] = analysis["estimated_revenue_l365d"]
fallback_revenue = analysis["nightly_price"] * analysis["occupancy_rate"] * 365
analysis["annual_revenue"] = analysis["annual_revenue"].where(analysis["annual_revenue"].gt(0), fallback_revenue)

property_type_mask = analysis["property_type_clean"].str.contains(
    "condo|rental unit|home|townhouse|guest suite|serviced apartment|loft|bungalow|cottage|apartment",
    regex=True,
    na=False,
)

base = analysis[
    analysis["room_type"].eq("Entire home/apt")
    & property_type_mask
    & analysis["nightly_price"].between(50, 1500)
    & analysis["occupancy_rate"].between(0, 1)
    & analysis["annual_revenue"].between(1000, 250000)
    & analysis["bedroom_count"].notna()
].copy()

def feasibility_rule(row):
    city = row["city_key"]
    bedrooms = int(row["bedroom_count"])
    group = str(row["neighbourhood_group_cleansed"]).lower()

    if city == "hawaii" and bedrooms in [0, 1]:
        return "Hawaii: $500K is most realistic for studio or 1BR condo/apartment-style units."
    if city == "san_francisco" and bedrooms in [0, 1]:
        return "San Francisco: $500K is most realistic for a studio or very small 1BR."
    if city == "new_york":
        if "manhattan" in group and bedrooms in [0, 1]:
            return "New York Manhattan: $500K is most realistic for studio or small 1BR."
        if "manhattan" not in group and bedrooms in [0, 1, 2]:
            return "New York outer boroughs: $500K can plausibly reach 1-2BR units."
    if city == "los_angeles" and bedrooms in [1, 2]:
        return "Los Angeles: $500K can plausibly reach 1-2BR condo/apartment-style units."
    if city == "nashville" and bedrooms in [2, 3, 4]:
        return "Nashville: $500K can plausibly reach larger 2-4BR homes or condos."
    return ""

base["budget_feasible_rule"] = base.apply(feasibility_rule, axis=1)
budget_feasible = base[base["budget_feasible_rule"].ne("")].copy()
budget_feasible.to_csv(processed_dir / "step1_budget_feasible_listing_metrics.csv", index=False)

def p25(series):
    return series.quantile(0.25)

def p75(series):
    return series.quantile(0.75)

segments = budget_feasible.groupby(
    [
        "city_key",
        "City",
        "neighbourhood_cleansed",
        "neighbourhood_group_cleansed",
        "property_type",
        "bedroom_count",
        "budget_feasible_rule",
    ],
    dropna=False,
).agg(
    comp_count=("id", "nunique"),
    median_nightly_price=("nightly_price", "median"),
    p25_nightly_price=("nightly_price", p25),
    p75_nightly_price=("nightly_price", p75),
    median_occupancy_rate=("occupancy_rate", "median"),
    p25_occupancy_rate=("occupancy_rate", p25),
    p75_occupancy_rate=("occupancy_rate", p75),
    median_annual_revenue=("annual_revenue", "median"),
    p25_annual_revenue=("annual_revenue", p25),
    p75_annual_revenue=("annual_revenue", p75),
    median_review_score=("review_scores_rating", "median"),
    median_reviews_per_month=("reviews_per_month", "median"),
    median_number_of_reviews=("number_of_reviews", "median"),
    median_calendar_days=("calendar_days", "median"),
).reset_index()

segments["bedrooms"] = segments["bedroom_count"].astype(int)
segments["sample_reliability"] = np.where(
    segments["comp_count"] >= 50,
    "strong",
    np.where(segments["comp_count"] >= 25, "usable", "thin"),
)
segments["downside_gap"] = segments["median_annual_revenue"] - segments["p25_annual_revenue"]
segments["upside_gap"] = segments["p75_annual_revenue"] - segments["median_annual_revenue"]
segments["annual_revenue_iqr"] = segments["p75_annual_revenue"] - segments["p25_annual_revenue"]
segments["risk_adjusted_revenue"] = (
    segments["median_annual_revenue"] / segments["annual_revenue_iqr"].replace(0, np.nan)
)

decision_segments = segments[
    (segments["comp_count"] >= 25)
    & (segments["median_review_score"].fillna(0) >= 4.5)
].copy()
decision_segments = decision_segments.sort_values(
    ["median_annual_revenue", "median_occupancy_rate", "comp_count"],
    ascending=False,
)

segments.to_csv(processed_dir / "step1_all_budget_feasible_candidate_segments.csv", index=False)
decision_segments.to_csv(processed_dir / "step1_decision_ready_candidate_segments.csv", index=False)
decision_segments.head(25).to_csv(results_dir / "step1_top_candidate_segments.csv", index=False)

summary_by_city = decision_segments.groupby(["city_key", "City"], dropna=False).agg(
    candidate_segments=("city_key", "size"),
    median_segment_revenue=("median_annual_revenue", "median"),
    best_segment_revenue=("median_annual_revenue", "max"),
    median_segment_occupancy=("median_occupancy_rate", "median"),
    total_comps=("comp_count", "sum"),
).reset_index().sort_values("best_segment_revenue", ascending=False)
summary_by_city.to_csv(results_dir / "step1_city_candidate_summary.csv", index=False)

top = decision_segments.head(10)
report_path = reports_dir / "step1_budget_feasible_candidates.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Step 1: Budget-Feasible Candidate Segment Universe\n\n")
    handle.write("## Purpose\n\n")
    handle.write(
        "This step defines what a $500,000 investor can plausibly buy in each market, then ranks those "
        "feasible Airbnb segments by observed operating performance. Because the Airbnb dataset does not contain "
        "purchase prices, the budget is used as a feasibility screen rather than a true ROI calculation.\n\n"
    )
    handle.write("## Data Used\n\n")
    handle.write("- `data/processed/master_data.csv` is the source of truth for this step. It already merges listing attributes with calendar-derived operating fields.\n")
    handle.write("- `estimated_revenue_l365d` is used as observed annual revenue when available.\n")
    handle.write("- `occupancy_rate_proxy` and `estimated_occupancy_l365d` provide listing-level occupancy information.\n")
    handle.write("- Nightly price is inferred as `estimated revenue / estimated occupied nights` when possible; otherwise, listing `price` is used as the fallback.\n\n")
    handle.write("## Housing Feasibility Rules Used\n\n")
    handle.write("- Hawaii: studio to 1BR condo/apartment-style units.\n")
    handle.write("- New York: studio to 1BR in Manhattan; up to 2BR in outer boroughs.\n")
    handle.write("- San Francisco: studio to small 1BR.\n")
    handle.write("- Los Angeles: 1BR to 2BR condo/apartment-style units.\n")
    handle.write("- Nashville: 2BR to 4BR homes, townhouses, condos, or rental units.\n\n")
    handle.write("These rules are based on the current housing-market research supplied for the project, including Redfin's 2025 $500K buying-power comparison and Bankrate's 2025 state median home price data.\n\n")
    handle.write("## Airbnb Filters\n\n")
    handle.write("- Entire home/apartment listings only.\n")
    handle.write("- Plausible property types: condo, rental unit, home, townhouse, guest suite, serviced apartment, loft, bungalow, cottage, or apartment.\n")
    handle.write("- Nightly price between $50 and $1,500.\n")
    handle.write("- Calendar-derived occupancy proxy between 0% and 100%.\n")
    handle.write("- Computed annual revenue between $1,000 and $250,000.\n")
    handle.write("- Decision-ready segments require at least 25 comparable listings and median review score of at least 4.5.\n\n")
    handle.write("## Files Created\n\n")
    handle.write("- `data/processed/investment_decision/step1_calendar_listing_metrics.csv`\n")
    handle.write("- `data/processed/investment_decision/step1_budget_feasible_listing_metrics.csv`\n")
    handle.write("- `data/processed/investment_decision/step1_all_budget_feasible_candidate_segments.csv`\n")
    handle.write("- `data/processed/investment_decision/step1_decision_ready_candidate_segments.csv`\n")
    handle.write("- `results/investment_decision/step1_top_candidate_segments.csv`\n")
    handle.write("- `results/investment_decision/step1_city_candidate_summary.csv`\n\n")
    handle.write("## Results\n\n")
    handle.write(f"Budget-feasible listing records analyzed: {len(budget_feasible):,}\n\n")
    handle.write(f"All budget-feasible segments created: {len(segments):,}\n\n")
    handle.write(f"Decision-ready segments after sample/review filters: {len(decision_segments):,}\n\n")
    handle.write("Top decision-ready candidate segments:\n\n")
    for _, row in top.iterrows():
        handle.write(
            f"- {row['City']} / {row['neighbourhood_cleansed']} / "
            f"{row['property_type']} / {int(row['bedrooms'])}BR: "
            f"median annual revenue ${row['median_annual_revenue']:,.0f}, "
            f"median occupancy {row['median_occupancy_rate']:.1%}, "
            f"median nightly price ${row['median_nightly_price']:,.0f}, "
            f"{int(row['comp_count'])} comparable listings, "
            f"median review score {row['median_review_score']:.2f}.\n"
        )
    handle.write("\n## Interpretation\n\n")
    handle.write(
        "This step does not choose the final investment yet. It creates the defensible candidate universe using "
        "the merged master dataset's calendar-derived operating performance. The next step should use k-nearest-neighbor comparable listings to "
        "validate whether the highest-ranked segments are supported by similar individual properties, not just by segment medians.\n"
    )

print("Saved master-data-based Step 1 budget-feasible candidate segment outputs.")
print(processed_dir / "step1_decision_ready_candidate_segments.csv")
print(results_dir / "step1_top_candidate_segments.csv")
print(report_path)
'''

    result = execute_python_code(code, description="Step 1 master-data-based budget-feasible Airbnb candidate segments")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
