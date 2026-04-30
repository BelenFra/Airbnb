# Q2 — Which experience dimensions matter for near–5-star overall reviews?

## Answer (headline)

- **Target:** `is_high_overall` = 1 if `review_scores_rating >= 4.9` (about **49.7%** of listings with non-missing sub-scores).
- **Predictors:** Airbnb structured sub-scores — cleanliness, check-in, communication, location.
- **Model evidence:** Logistic regression (marginal coefficients) and Random Forest feature importance both rank drivers; top RF importance: **review_scores_cleanliness**; largest absolute logistic coefficient: **review_scores_cleanliness**.

Sub-scores are **correlated** with each other; coefficients are **associative**, not independent causal effects.

## Method

- Toolkit: `load_data` → prepared frame → `split_data` (70/15/15, seed 42) → `train_logistic_regression` + `train_random_forest` (classification).

## Evidence

- `q2_subscore_importance_ranking.csv` — logistic coefficients and RF importance.
- `q2_subscore_correlation_with_overall.csv` — pairwise correlation with overall rating.

### Logistic regression — metrics

| metric | value |
| --- | --- |
| intercept | -73.8123 |
| test_accuracy | 0.8243 |
| test_auc | 0.9053 |
| training_accuracy | 0.8184 |
| training_auc | 0.8998 |
| validation_accuracy | 0.8298 |
| validation_auc | 0.9056 |


### Logistic regression — coefficients

| feature | coefficient |
| --- | --- |
| review_scores_cleanliness | 5.1827 |
| review_scores_communication | 5.0111 |
| review_scores_checkin | 2.6021 |
| review_scores_location | 2.3485 |


### Logistic regression — Training confusion (TN / FP / FN / TP)

| TN | FP | FN | TP |
| --- | --- | --- | --- |
| 21425 | 6627 | 3488 | 24158 |


### Logistic regression — Validation confusion (TN / FP / FN / TP)

| TN | FP | FN | TP |
| --- | --- | --- | --- |
| 4609 | 1327 | 705 | 5295 |


### Random Forest — metrics

| metric | value |
| --- | --- |
| n_estimators | 150.0 |
| test_accuracy | 0.8446 |
| training_accuracy | 0.9336 |
| validation_accuracy | 0.8442 |


### Random Forest — feature importance

| feature | importance |
| --- | --- |
| review_scores_cleanliness | 0.4315 |
| review_scores_communication | 0.26 |
| review_scores_checkin | 0.1675 |
| review_scores_location | 0.141 |


## Business interpretation

Use the ranking as a **prioritisation lens** for where operational fixes **move the needle on guest perception**: if **cleanliness** and **accuracy/check-in** dominate, invest in **housekeeping QA** and **arrival experience** before marginal décor spend. **Location** is partly **fixed** by asset; message and price should reflect true access/noise trade-offs.
