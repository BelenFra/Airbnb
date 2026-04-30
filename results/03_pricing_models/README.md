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
