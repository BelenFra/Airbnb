# `results/03_pricing_models/` — Property and Pricing Questions

Outputs that answer the **Property and Pricing Questions** in the TP brief
and the supervised + k-NN methods (TP Section 4):

- What type of property should the client acquire (entire home / private
  room, # bedrooms)?
- What amenities have the biggest impact on price and occupancy?
- What nightly price maximises annual revenue (price elasticity)?
- How do *comparable* listings actually perform (k-NN sanity check)?

## Suggested artefacts

| File | Produced by | Describes |
| --- | --- | --- |
| `price_model_metrics.csv` | supervised script | RMSE / MAE / R² for ≥ 2 model families (e.g. random forest vs boosted trees). |
| `occupancy_model_metrics.csv` | supervised script | Same, but predicting occupancy proxy. |
| `feature_importances.csv` | supervised script | Top features per model with sign and magnitude. |
| `model_comparison_summary.csv` | supervised script | Side-by-side table of the chosen models with selected metrics. |
| `knn_comparables.csv` | k-NN script | For each candidate property profile: nearest neighbours' ID, neighborhood, ADR, occupancy, annual revenue. |
| `amenity_uplift.csv` | TBD | Marginal price / occupancy uplift per amenity (pool, parking, workspace, etc.). |
| `price_elasticity_curves.csv` | TBD | For the recommended segments, modelled annual revenue at a grid of nightly prices. |

## Conventions

- All models are reproducible with `random_state=42`.
- Train / test split is 80/20 stratified by city (or as documented per file).
- Metrics include the **business interpretation** in a paragraph in the
  final memo, not just the raw numbers.
- k-NN comparables are reported as **realised** revenue, not the model's
  prediction — this is the sanity check on the modelling pipeline.

# `results/03_pricing_models/` — Pricing Block

This folder contains the final deliverables for the **Pricing** block of the Airbnb investment project.

## Business questions addressed

This block focuses on the pricing side of the investment decision:

- Which listing characteristics are most strongly associated with higher nightly price?
- How do pricing drivers vary across cities?
- How do room type, capacity, and amenities shape pricing power?
- How do nightly price, estimated occupancy, and annual revenue proxy line up descriptively across listings?

## Main memo

- `pricing_final_integrated_memo.md`  
  Main integrated memo for the pricing block. This is the primary narrative document in this folder.

## Supporting files

### Predictive pricing model
- `model_comparison_table.csv` — final model comparison (Random Forest vs boosted trees)
- `feature_importance_permutation_validation.csv` — validation-based feature importance for the selected model
- `summary_city_entire_minus_private_gap.csv` — city-level entire-home vs private-room pricing gap
- `amenities_parse_summary_metrics.csv` — amenity parsing quality metrics used in the pricing analysis

### Descriptive price / occupancy / revenue analysis
- `02_correlation_pearson.csv` — descriptive correlations among price, estimated occupancy, and annual revenue proxy
- `03_summary_by_city.csv` — descriptive summary by city
- `04_summary_by_room_type.csv` — descriptive summary by room type
- `05_price_bands_tertiles_overall.csv` — global price-band summary using tertiles
- `05b_price_band_cutpoints_global.csv` — cutpoints used to define the tertile bands

### Figures
- `pricing_final_feature_importance_figure.png`
- `pricing_final_city_comparison_figure.png`
- `pricing_final_price_band_figure.png`

These figures are referenced in the integrated memo and support team review of the pricing results.

## Interpretation guidance

This folder combines:
1. **predictive modeling evidence** for nightly price, and
2. **descriptive evidence** on price, estimated occupancy, and annual revenue proxy.

Important caution:
- feature importance is **predictive**, not causal
- the price–occupancy–revenue relationship shown here is **descriptive**, not a formal causal elasticity estimate
- listed nightly price is a scraped ask price, not necessarily realized transaction price
- estimated occupancy and annual revenue are proxy-style measures, not audited operating outcomes

## Scope note

This folder supports the pricing block only. It does **not** fully answer:
- causal price elasticity
- k-NN comparables
- review-driven performance questions
- the final integrated investment recommendation

Those questions are handled elsewhere in the broader project.
