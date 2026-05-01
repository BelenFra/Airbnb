# AI Usage Appendix

**Course:** MBA 706 — Data Analytics: Tools and Opportunities
**Project:** Where Should I Invest in Airbnb? An End-to-End Data Analytics Project
**Team:** Tomas Ignacio Latorre, Belen Franco, Agostino Cascio, Alexander Ruiz, Will Wang
**Submission date:** May 1, 2026

This appendix documents how our team used AI tools throughout the term project, in compliance with the AI Usage Policy in Section 8 of the project brief. We used AI extensively, and we are fully accountable for every number, chart, model, and recommendation in our submitted memo and slides.

## 1. Tools used

| Tool | Where it was used | Role |
|---|---|---|
| **Cursor IDE** | All Python scripting, EDA, modeling, debugging, memo drafting, repo refactoring | Primary working environment for the entire project |
| **Cursor agent — Claude Opus 4.7** (Anthropic) | Code generation, methodology design, business interpretation, memo writing | Primary analytical and writing assistant |
| **Cursor agent — GPT 5.5** (OpenAI) | Cross-review of outputs, sanity checks on numbers and narrative consistency, second-opinion on methodology | Secondary reviewer / verifier |
| **GitHub** | Version control, peer review, branching per block, pull-request workflow | Collaboration and audit trail |
| **Inside Airbnb** ([insideairbnb.com](https://insideairbnb.com/get-the-data)) | Source for `listings.csv.gz`, `reviews.csv.gz`, `calendar.csv.gz` per city | Public dataset (CC BY 4.0) |
| **External housing-price research** (Zillow / Realtor.com public listings, accessed Q1–Q2 2026) | Block 5 budget-feasibility rules ($500K → property type/size by city) | Reference for constraints not in Airbnb data |

Every line of Python code, every chart, every memo paragraph, and every CSV in `results/` and `reports/figures/` was produced inside Cursor. No external GPT/Claude web sessions, Copilot inline completions, or third-party AI tools were used outside the Cursor environment.

## 2. Use by project block

The project is organized into five analytical blocks. Each block was owned by one team member, who used Cursor + the AI agents above as their main tooling. All teammates reviewed each other's work via pull requests before merge.

| Block | Owner | AI use |
|---|---|---|
| **Cleaning pipeline** (`scripts/cleaning/`, `data/processed/`) | Belen Franco, Tomas Ignacio Latorre, Agostino Cascio, Will Wang | Generated chunked readers for large `reviews.csv.gz` and `calendar.csv.gz`, fixed CSV-quoting bug (`csv.QUOTE_ALL`), implemented outlier clipping for calendar, built `master_data.csv` join, and wrote per-asset `*_cleaning_decisions.md` memos. |
| **Block 1 — Market analysis (Q1–Q4)** (`scripts/market_analysis/`, `results/01_market_analysis/`) | Tomas Ignacio Latorre | Designed and implemented the four scripts (risk-adjusted revenue, price/occupancy/revenue, saturation index, seasonality). AI helped with median/IQR robust ratio, HHI, coefficient of variation, partial-month filtering, and bubble-chart layout. |
| **Block 2 — Segmentation** (`scripts/models/segmentation_kmeans.py`, `results/02_segmentation/`) | Will Wang | K-Means with elbow + silhouette, business-named clusters, neighborhood ranking via z-score weighted composite, supply-demand gap classification. AI helped disambiguate duplicate cluster names ("Premium mid-size active" vs "slow-turn"). |
| **Block 3 — Pricing models** (`scripts/models/*_property_pricing*.py`, `results/03_pricing_models/`) | Alexander Ruiz | Random Forest vs Histogram Gradient Boosting on log(price); permutation-based feature importance; price-band tertile descriptive analysis. AI helped with model comparison framing and feature-importance interpretation. |
| **Block 4 — Guest experience & text analytics** (`scripts/04_guest_experience/`, `scripts/models/text_analysis/`, `results/04_guest_experience/`) | Belen Franco | Regex complaint-cue detection, TF-IDF at listing/city level (with Porter stemming), Logistic Regression and Random Forest for high-rating drivers, amenity-flag operational signals, and top-performer term lift. AI helped design the hierarchical TF-IDF pipeline and chunked-review reader. |
| **Block 5 — Investment decision** (`reports/investment_decision/`, `reports/figures/05_investment_decision/`) | Agostino Cascio | Budget-feasibility filter (external housing research), k-NN comparable-listing validation, bootstrap revenue scenarios (conservative / moderate / optimistic), normalized weighted risk score, two-property portfolio with efficient-frontier-style comparison. AI helped frame the portfolio logic and bootstrap CI. |
| **Consolidated memo** (`reports/consolidated_airbnb_investment_memo.md`) | Tomas Ignacio Latorre, Belen Franco, Agostino Cascio, Alexander Ruiz, Will Wang | Synthesized all five blocks into the integrated investor memo, including statistical-methods summaries and figure placement. AI helped weave the narrative funnel (market → segment → pricing → guest experience → decision). Each owner reviewed the section corresponding to their block before sign-off. |

## 3. Representative prompts and workflows

We did not log every prompt, but the following are representative of the workflows we used. Each one was followed by manual code review, execution, output inspection, and iteration before being committed.

- *Cleaning:* "The reviews CSV has unescaped newlines inside the `comments` field, breaking downstream parsing into a `bad_listing_id` column. Patch `run_full_review_cleaning.py` to write with `csv.QUOTE_ALL` and apply the same fix to the listing and calendar pipelines."
- *Block 1:* "Build `q1_risk_adjusted_revenue.py` that reads `master_data.csv`, computes per-listing annual revenue as `price × occupancy_rate × 365`, then ranks the five cities using a robust median / IQR ratio. Output a CSV, a 1-page markdown memo, and three plots (boxplot, ranking bar chart, return-vs-risk bubble chart with bubble size proportional to listing count)."
- *Block 2:* "Cluster listings with K-Means on standardized listing features. Justify k via elbow and silhouette but pick a business-interpretable value. Auto-name each cluster from its centroid (capacity tier × price tier × occupancy tier) and warn if two clusters end up with the same name."
- *Block 3:* "Train a Random Forest and a Histogram Gradient Boosting model on `log(price)` with the same train/val/test split. Select by validation R², report test R², and run permutation importance on the validation set."
- *Block 4:* "Aggregate cleaned reviews into per-listing documents, run TF-IDF, and compute distinctive vocabulary at listing-vs-city level. Then train a logistic regression and a Random Forest classifier for `overall_rating ≥ 4.9` using the structured sub-scores. Report AUC and feature importance."
- *Block 5:* "Filter the segments to those that fit a $500K budget per city, rank by median annual revenue, validate the top candidate with k-NN on raw listings, then build conservative/moderate/optimistic scenarios with a bootstrap CI. Finally, compare two-property portfolios on revenue, risk score, and city occupancy correlation."
- *Memo writing:* "Draft a 5–8 page integrated investor memo that explains the project as a narrowing funnel (market → segment → pricing → guest experience → decision). Cite the figures and CSVs that already exist in `results/` and `reports/figures/`, and add a 'Statistical methods used' subsection per block."

## 4. Accountability statement

The AI tools accelerated implementation, drafting, and refactoring, but every analytical decision, every business interpretation, every reported number, and the final investment recommendation were reviewed, validated, and signed off by the team. We cross-checked critical figures (Hawaii median revenue, saturation score, Hollywood Hills West k-NN comparable, two-property portfolio risk) against the underlying CSVs in `results/`. Any error in our submission is our responsibility, not the tools'.

We also note three explicit limitations introduced by our AI-assisted workflow:

1. AI-generated initial code was sometimes inconsistent with our project conventions (paths, file discipline). We caught and fixed these in PR review (see audit history in git log).
2. The memo recommendation depends on **external housing-price research** to translate the $500K budget into property configurations per city. That research was conducted manually by the team using public sources; the AI was not relied on to generate property prices.
3. The pricing and high-rating models are **predictive and associative**, not causal. The AI was instructed to frame interpretations accordingly, and we re-checked this in the final memo.
