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

    listing_result = load_data(str(listing_metrics_path), dataset_name="step1_listing_metrics")
    if listing_result.get("status") != "success":
        raise RuntimeError(listing_result)

    segment_result = load_data(str(top_segments_path), dataset_name="step1_top_segments")
    if segment_result.get("status") != "success":
        raise RuntimeError(segment_result)

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
processed_dir.mkdir(parents=True, exist_ok=True)
results_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)

listings = _data_store["step1_listing_metrics"].copy()
segments = _data_store["step1_top_segments"].copy().head(5)

for col in [
    "id",
    "bedroom_count",
    "bathrooms",
    "beds",
    "nightly_price",
    "occupancy_rate",
    "annual_revenue",
    "review_scores_rating",
    "reviews_per_month",
    "number_of_reviews",
]:
    if col in listings.columns:
        listings[col] = pd.to_numeric(listings[col], errors="coerce")

for col in [
    "bedroom_count",
    "median_nightly_price",
    "median_occupancy_rate",
    "median_annual_revenue",
    "median_review_score",
    "median_reviews_per_month",
]:
    if col in segments.columns:
        segments[col] = pd.to_numeric(segments[col], errors="coerce")

feature_columns = [
    "bedroom_count",
    "bathrooms",
    "beds",
    "nightly_price",
    "occupancy_rate",
    "review_scores_rating",
    "reviews_per_month",
]

all_neighbors = []
validation_rows = []
for rank, segment in enumerate(segments.to_dict(orient="records"), start=1):
    same_city = listings["city_key"].eq(segment["city_key"])
    same_neighborhood = listings["neighbourhood_cleansed"].eq(segment["neighbourhood_cleansed"])
    same_property = listings["property_type"].eq(segment["property_type"])
    same_bedrooms = listings["bedroom_count"].eq(segment["bedroom_count"])

    pool = listings[same_city & same_neighborhood & same_property & same_bedrooms].copy()
    match_scope = "same city, neighborhood, property type, and bedrooms"
    if len(pool) < 15:
        pool = listings[same_city & same_neighborhood & same_bedrooms].copy()
        match_scope = "same city, neighborhood, and bedrooms"
    if len(pool) < 15:
        pool = listings[same_city & same_property & same_bedrooms].copy()
        match_scope = "same city, property type, and bedrooms"
    if len(pool) < 15:
        pool = listings[same_city & same_bedrooms].copy()
        match_scope = "same city and bedrooms"

    pool = pool.dropna(subset=["annual_revenue", "nightly_price", "occupancy_rate"]).copy()
    if pool.empty:
        continue

    target = {
        "bedroom_count": segment["bedroom_count"],
        "bathrooms": pool["bathrooms"].median(),
        "beds": pool["beds"].median(),
        "nightly_price": segment["median_nightly_price"],
        "occupancy_rate": segment["median_occupancy_rate"],
        "review_scores_rating": segment["median_review_score"],
        "reviews_per_month": segment["median_reviews_per_month"],
    }

    usable_features = [col for col in feature_columns if col in pool.columns and pd.notna(target.get(col))]
    feature_frame = pool[usable_features].copy()
    for col in usable_features:
        feature_frame[col] = feature_frame[col].fillna(feature_frame[col].median())
    medians = feature_frame.median()
    iqrs = feature_frame.quantile(0.75) - feature_frame.quantile(0.25)
    scales = iqrs.replace(0, np.nan).fillna(feature_frame.std().replace(0, np.nan)).fillna(1)

    target_series = pd.Series({col: target[col] for col in usable_features})
    standardized = (feature_frame - medians) / scales
    target_standardized = (target_series - medians) / scales
    pool["knn_distance"] = np.sqrt(((standardized - target_standardized) ** 2).sum(axis=1))
    pool = pool.sort_values(["knn_distance", "annual_revenue"], ascending=[True, False])
    neighbors = pool.head(15).copy()
    neighbors["candidate_rank"] = rank
    neighbors["candidate_segment"] = (
        f"{segment['City']} / {segment['neighbourhood_cleansed']} / "
        f"{segment['property_type']} / {int(segment['bedroom_count'])}BR"
    )
    neighbors["match_scope"] = match_scope
    all_neighbors.append(neighbors)

    validation_rows.append(
        {
            "candidate_rank": rank,
            "candidate_segment": neighbors["candidate_segment"].iloc[0],
            "match_scope": match_scope,
            "candidate_segment_median_revenue": segment["median_annual_revenue"],
            "candidate_segment_median_price": segment["median_nightly_price"],
            "candidate_segment_median_occupancy": segment["median_occupancy_rate"],
            "knn_comp_count": len(neighbors),
            "knn_median_revenue": neighbors["annual_revenue"].median(),
            "knn_p25_revenue": neighbors["annual_revenue"].quantile(0.25),
            "knn_p75_revenue": neighbors["annual_revenue"].quantile(0.75),
            "knn_median_price": neighbors["nightly_price"].median(),
            "knn_median_occupancy": neighbors["occupancy_rate"].median(),
            "knn_median_review_score": neighbors["review_scores_rating"].median(),
            "revenue_validation_gap": neighbors["annual_revenue"].median() - segment["median_annual_revenue"],
        }
    )

neighbors_df = pd.concat(all_neighbors, ignore_index=True)
validation_df = pd.DataFrame(validation_rows)
validation_df["validation_status"] = np.where(
    validation_df["knn_median_revenue"] >= validation_df["candidate_segment_median_revenue"] * 0.9,
    "supported by close comps",
    "weaker than segment median in close comps",
)

neighbor_columns = [
    "candidate_rank",
    "candidate_segment",
    "match_scope",
    "id",
    "listing_url",
    "City",
    "neighbourhood_cleansed",
    "property_type",
    "bedroom_count",
    "bathrooms",
    "beds",
    "nightly_price",
    "occupancy_rate",
    "annual_revenue",
    "review_scores_rating",
    "reviews_per_month",
    "number_of_reviews",
    "knn_distance",
]
neighbor_columns = [col for col in neighbor_columns if col in neighbors_df.columns]

neighbors_df[neighbor_columns].to_csv(
    processed_dir / "step2_knn_comparable_listings.csv",
    index=False,
)
validation_df.to_csv(
    results_dir / "step2_knn_candidate_validation_summary.csv",
    index=False,
)

report_path = reports_dir / "step2_knn_comparable_validation.md"
with report_path.open("w", encoding="utf-8") as handle:
    handle.write("# Step 2: k-NN Comparable Listing Validation\n\n")
    handle.write("## Purpose\n\n")
    handle.write(
        "Step 1 ranked budget-feasible candidate segments. Step 2 checks whether those segment-level "
        "recommendations are supported by similar individual listings. This is important because a segment median "
        "can look attractive even when the closest actual listings perform differently.\n\n"
    )
    handle.write("## Method\n\n")
    handle.write("- Took the top 5 Step 1 candidate segments.\n")
    handle.write("- Built a comparable-listing pool for each candidate, prioritizing same city, neighborhood, property type, and bedroom count.\n")
    handle.write("- Used a k-nearest-neighbor distance based on bedroom count, bathrooms, beds, nightly price, occupancy, review score, and reviews per month.\n")
    handle.write("- Selected the 15 closest comparable listings for each candidate.\n")
    handle.write("- Compared k-NN median revenue with the Step 1 segment median revenue.\n\n")
    handle.write("## Files Created\n\n")
    handle.write("- `data/processed/investment_decision/step2_knn_comparable_listings.csv`\n")
    handle.write("- `results/investment_decision/step2_knn_candidate_validation_summary.csv`\n\n")
    handle.write("## Results\n\n")
    for row in validation_df.to_dict(orient="records"):
        handle.write(
            f"- {row['candidate_segment']}: Step 1 median revenue ${row['candidate_segment_median_revenue']:,.0f}; "
            f"k-NN median revenue ${row['knn_median_revenue']:,.0f}; "
            f"k-NN revenue range ${row['knn_p25_revenue']:,.0f}-${row['knn_p75_revenue']:,.0f}; "
            f"status: {row['validation_status']}.\n"
        )
    handle.write("\n## Interpretation\n\n")
    handle.write(
        "Candidates whose k-NN median revenue is close to the segment median are more credible because similar real listings support the segment result. "
        "Candidates with weaker k-NN performance should be treated cautiously or moved behind better-supported alternatives.\n"
    )

print("Saved Step 2 k-NN comparable validation outputs.")
print(processed_dir / "step2_knn_comparable_listings.csv")
print(results_dir / "step2_knn_candidate_validation_summary.csv")
print(report_path)
'''

    result = execute_python_code(code, description="Step 2 k-NN comparable listing validation")
    if result.get("status") != "success":
        raise RuntimeError(result)
    print(result)


if __name__ == "__main__":
    main()
