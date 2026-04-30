# Property / Pricing Evidence Pack

Internal support document summarizing finalized model metrics, driver visuals, and market/amenities context pulled from repository outputs. **No models were retrained.**

---

## 1. Final model comparison (Random Forest vs boosted trees)

**Why it matters:** Establishes the validated champion for `log(price)` and shows how gradient boosted alternatives compare on the **same stratified splits** — essential context before drafting the group memo or client slides.

| model | train_r2 | val_r2 | val_rmse | test_r2 | test_rmse | test_mae |
|---|---|---|---|---|---|---|
| RF_deeper_frac_features | 0.956586 | 0.846149 | 0.383776 | 0.838584 | 0.383654 | 0.253052 |
| HistGBDT_deeper_faster_lr | 0.876078 | 0.842420 | 0.388400 | 0.837293 | 0.385185 | 0.265773 |
| HistGBDT_moderate_depth | 0.828281 | 0.815156 | 0.420660 | 0.810610 | 0.415570 | 0.287867 |
| RF_shallow_sqrt_features | 0.750493 | 0.732747 | 0.505812 | 0.730387 | 0.495834 | 0.346785 |

_Champion: **RF_deeper_frac_features** (highest validation R²; tie-break: lower validation RMSE). Train / validation / test = 62,100 / 20,700 / 20,700 rows. Metrics are on **`log(price)`**._

---

## 2. Top pricing drivers (clean visual)

**Why it matters:** Permutation importance on the champion model summarizes **marginal explanatory power** after one-hot preprocessing — a team-friendly counterpart to coefficient tables.

![Top permutation drivers](property_pricing_evidence_assets/evidence_chart_top_permutation_drivers.png)

---

## 3. City-level comparison (visual + tables)

**Why it matters:** Demonstrates heterogeneous **pricing levels** and **entire-home vs private-room uplifts** across the five-city panel — reinforces that comps and underwriting must reference **metro-specific** patterns.

![City pricing comparison](property_pricing_evidence_assets/evidence_chart_city_pricing_patterns.png)

**Companion — mean log(price) by city** (EDA structural-filter cohort; see `eda/summary_logprice_by_city.csv`):

| City | count | mean | std | median |
|---|---|---|---|---|
| Hawaii | 33113 | 5.6338 | 1.0223 | 5.451 |
| Los Angeles | 36750 | 5.1176 | 0.8955 | 5.0434 |
| Nashville | 6623 | 5.1067 | 0.6355 | 5.0626 |
| New York | 21313 | 5.1283 | 0.9872 | 5.037 |
| San Francisco | 5793 | 5.2018 | 0.8087 | 5.1358 |

**Companion — entire-home minus private room (Δ mean log price)** (see `eda/summary_city_entire_minus_private_gap.csv`):

| City | gap_mean_log_price |
|---|---|
| Hawaii | 0.2109 |
| Los Angeles | 1.0607 |
| Nashville | 0.8475 |
| New York | 0.8099 |
| San Francisco | 0.7545 |

---

## 4. Amenities summary (tables + visual)

**Why it matters:** Validates engineering hygiene (parse reliability) and shows how **breadth vs flag-level amenities** line up against nightly price conditional on hedonic controls.

| QA metric | Value |
| --- | --- |
| Strict JSON-array parse success (full master analytic) | 99.9672% |
| Rows failing strict parse | 34 |
| Median amenity tokens (successful parses) | ~38 (see `eda/amenities_parse_distribution.txt`) |

![Amenity permutation importance](property_pricing_evidence_assets/evidence_chart_amenity_permutation.png)

---

## Audit trail — source artifacts

| Artifact | Relative path |
| --- | --- |
| Model leaderboard | `modeling/training_outputs_property_pricing/model_comparison_table.csv` |
| Permutation rankings | `modeling/training_outputs_property_pricing/feature_importance_permutation_validation.csv` |
| City aggregates | `eda/summary_logprice_by_city.csv`, `eda/summary_city_entire_minus_private_gap.csv` |
| Amenities QA | `eda/amenities_parse_summary_metrics.csv` |

**Figure files:** `evidence_chart_top_permutation_drivers.png`, `evidence_chart_city_pricing_patterns.png`, `evidence_chart_amenity_permutation.png`.
