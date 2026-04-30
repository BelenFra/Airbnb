# `results/` — Analytical outputs that feed the investment memo

This folder holds the **analytical** outputs of the term project: cluster
profiles, model metrics, sentiment / topic tables, revenue scenarios, and the
final investment recommendation. Plots (PNG/PDF) live in `reports/figures/`,
the project memo lives in `reports/`, and intermediate processed data lives
in `data/processed/`.

The TP brief (Section 2) tells us to **organise the memo around business
questions, not around analytical methods**. So the subfolders below mirror
the five business-question groups in the brief, plus one auxiliary folder
for cleaning audits.

## Layout

| Folder | Business question(s) | What goes here |
| --- | --- | --- |
| `01_market_analysis/` | Market-Level Questions | Cross-city revenue potential, seasonality, competitive saturation, recovery profiles. Cross-city EDA tables and summary stats. **Also** hosts cleaning audits in `listing/`, `calendars/`, `reviews/` subfolders (kept here because the orchestrator hard-codes these paths). |
| `02_segmentation/` | Neighborhood / Segment Questions | Cluster profiles (k-means), neighborhood rankings, segment-level revenue tables, oversaturated vs underserved segments. |
| `03_pricing_models/` | Property / Pricing Questions | Supervised model metrics (price / occupancy), feature importances, model comparison tables, k-NN comparable-listings tables. |
| `04_guest_experience/` | Guest Experience Questions | Sentiment by city / property type, topic-model keywords, complaint / praise rankings, operational-investment payoff tables. |
| `05_investment_decision/` | Investment Decision Questions | Final recommended property profile, revenue scenarios (conservative / moderate / optimistic), risk register, two-property diversification analysis. |

> **Convention:** keep the analytical folders organised by business question
> even when one analysis uses several methods. For example, "Which neighborhood
> in NYC has the best revenue potential?" mixes clustering, kNN and revenue
> projection — its outputs all go in `01_market_analysis/` (or `02_segmentation/`,
> depending on the angle of the answer), **not** scattered across one folder
> per method.

## Naming conventions

- **Files:** snake_case, descriptive, prefixed with the artefact type when
  helpful: `cluster_profiles.csv`, `price_model_metrics.csv`,
  `topic_keywords_by_city.csv`, `revenue_scenarios.csv`.
- **City tokens** inside files use the project-wide snake_case slugs
  (`hawaii`, `los_angeles`, `nashville`, `new_york`, `san_francisco`).
- **Each folder gets its own `README.md`** describing what artefacts live
  there and which scripts produce them. See the per-folder READMEs.

## What does NOT belong here

- **Plots / figures** → `reports/figures/<topic>/`.
- **Final memo / slides** → `reports/`.
- **Intermediate cleaned data** → `data/processed/`.
- **EDA notebooks** → `notebooks/`.
- **Raw quality memos** (e.g. `raw_data_memo_reviews.md`) → live next to the
  data they describe (`data/raw/<dataset>/_eda/` or `data/processed/<dataset>/_eda/`).
