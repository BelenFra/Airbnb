# Property / Pricing Block — Internal Team Memo (Detailed)

**Status:** Working paper for internal review — not the final consolidated group memo.  
**Audience:** Project team reviewing scope, rigor, and business read-through of the Property / Pricing analytic block.  
**Authoritative modeling run:** Outputs in `modeling/training_outputs_property_pricing/` (no re-training in this memo).

---

## 1. TL;DR / bottom line

- We treated **short-term rental nightly economics** through a disciplined **pricing (hedonic) lens**: predict **`log(price)`** from **listing structure, geography, policy, operator signals, and engineered amenities**, with **identifiers and leakage-prone columns excluded** ahead of modeling.
- The **preferred learner** among four specifications is **`RF_deeper_frac_features`**: validation **R² ≈ 0.846**, validation **RMSE ≈ 0.384 log-units**, held-out test **R² ≈ 0.839**, test **RMSE ≈ 0.384**, test **MAE ≈ 0.253**. **Model selection followed validation performance**, not test.
- Two **histogram gradient boosted** specifications were credible challengers (**validation R² ≈ 0.815–0.842**) but **did not outperform the deeper Random Forest on validation**.
- **Top pricing drivers** (stable across RF split importances *and* validation permutation importance) emphasize **guest capacity**, **geo / micro-location**, **bathrooms and sleeping inventory**, **`room_type` / `property_type`**, **host portfolio scale**, and **minimum/maximum-night policy fields**. **`amenity_count`** and **`pool`** contribute after those fundamentals — **individual amenity binaries are smaller** apart from **`pool`** ranking high among flags.
- **Markets behave differently.** Descriptive cohort analysis shows **widely divergent entire-home minus private-room mean log(price) gaps** by city (≈ **0.21 log-units for Hawaii vs >1.05 for Los Angeles** in pre-modeling cohort counts), implying **localized strategy** beats one national comps template.
- **Investor takeaway:** The model acts as **associative comps intelligence**, not causal ROI — use it to sanity-check ADR positioning **after** structure, location, and product type filters, aligned with **`revenue ≈ nightly price × realized booked nights`** (conceptually analogous to **`price × intensity × horizon`**).

---

## 2. Business question this block answers

**Primary framing:** Among active listings scraped into our consolidated master dataset, **what observable property, geo, inventory, operator, policy, and amenity attributes co-move most strongly with nightly price** once we deliberately avoid tautological constructs?

**Supporting questions surfaced in framing:**

- How do **product archetypes** (**entire home vs private room** vs other modes) reposition against each other inside and across metro cohorts?
- Where do **investors add lift** versus **risk** — incremental bedrooms, repositioned amenities, tightening minimum stays?

This block explicitly **sizes and explains dispersion in nightly ask** (**`price` / `log(price)`**) under a **prediction-oriented** paradigm. It does **not** claim causal effects of renovating or rebranding listings.

---

## 3. Data used and scope of this block

### Source lineage

| Layer | Artifact / path | Role |
|-------|------------------|------|
| Raw integration | `master_data.csv` (read-only upstream) | Cross-metro scraping integration |
| Modeling spec | `property_pricing_modeling_spec.txt` | Target definition, predictor policy, exclusions |
| EDA QA | `eda/` outputs (filters, summaries, mismatch rows) | Filter accounting, stratification QA, descriptive price views |
| Final modeling matrix | `modeling/property_pricing_modeling_dataset.csv` | **43 predictor columns** (+ lineage + targets) consumed by supervised learners |

### Rows and exclusions (authoritative modeling cohort)

Building on `modeling/property_pricing_dataset_preparation_summary.txt`:

- **Imported from master:** 103,708 listing rows (`id` uniqueness verified upstream).
- **Structural filters:** 116 rows cumulatively excluded (negative/zero price guardrails, extreme bedroom/bathroom/plausibility rules consistent with modeling spec §4).
- **Occupancy / calendar scaffolding QA:** **92 listings** flagged where **`occupancy_rate_proxy`** disagreed materially with **`(365 − availability_365) / 365`** (threshold 0.01). **Dropped conservatively** even though nightly-price **`X`** omits calendar fields outright — avoids training on contradictory listing scaffolding.
- **Final modeling cohort:** **103,500 listings** modeled as CSV rows.

Pre-model EDA analytic sample (prior to the 92-row occupancy guard) totaled **103,592** filtered rows — used for exploratory tables (e.g. city-level summaries) that underpin **Sections 8–9** narrative; wording below notes when figures reference **that slightly larger pre-guard analytic slice**.

### Targets and withheld columns

| Item | Handling |
|------|----------|
| **Primary modeled target** | **`log_price`** (natural log of nightly **`price`** after positivity filters). |
| **Reporting aid** | Raw **`price`** retained in dataset **only outside** predictor matrix. |
| **Identifiers** | **`listing_id`**, **`host_id`** excluded from **`X`** (training script). |

### Markets

Five metro labels in **`City`**: Hawaii, Los Angeles, New York, Nashville, San Francisco (each historically aligned one-to-one with an upstream scrape batch; we use **`City`** in the learner and withheld **`scrape_id`** per modeling spec redundancy).

---

## 4. Short approach overview

1. **Specification discipline** aligned to `property_pricing_modeling_spec.txt`: core hedonic listing predictors retained; leakage / redundancy (**e.g.** `estimated_revenue_l365d`), broken host-rate scrape columns, occupancy/calendar surrogates, opaque URLs, and review blocks excluded from nightly-price **`X`**.
2. **`log(price)`** chosen as modeled response for numerical stability (**heavy skew** in nominal dollars flagged in pricing EDA: skewness of raw **`price`** roughly **order 10+,** **`log(price)`** skewness nearer **~1.6** post filters).
3. **Feature plumbing:** stratified **`City × room_type`** train/validation/test partitioning (rare combos bucketed **<25 listings** → `__rare_city_room_combo`); categorical high-cardinality one-hot pipelines; median imputed numerics; **amenities extracted** strictly from Airbnb JSON blobs into **counts + curated binary indicators** (**pool**, **parking**, **workspace**, …) per dataset build (`scripts/build_property_pricing_modeling_dataset.py`).
4. **Model zoo:** identical preprocessing feeding **four** supervised learners (**two RandomForestRegressor configs**, **two HistGradientBoostingRegressor configs**) via `scripts/train_property_pricing_rf_vs_boost.py`.
5. **Champion crowned on validation **`R²`**, RMSE tie-break.** Test metrics reported **transparently**, but never used as the selection oracle.
6. **Interpretation layering:** **`feature_importance_native_aggregated.csv`** (winner RF internal splitter signal), **`feature_importance_permutation_validation.csv`** (shuffle-based validation stress test on **native column names**) — summarized jointly for Sections 7 & 9.

---

## 5. Model comparison: Random Forest vs Boosted Trees

**Split sizing** (`modeling/training_outputs_property_pricing/data_split_sizes.csv`): **Train 62,100** — **Validation 20,700** — **Test 20,700** **(≈ 60 % / 20 % / 20 %)** stratified proxies.

Full precision lives in **`modeling/training_outputs_property_pricing/model_comparison_table.csv`**. Rounded excerpts:

| Model | Train R² | Val R² | Val RMSE | Test R² | Test RMSE | Test MAE |
|-------|-----------|--------|----------|---------|-----------|-----------|
| **RF_deeper_frac_features** | **0.957** | **0.846** | **0.384** | **0.839** | **0.384** | **0.253** |
| HistGBDT_deeper_faster_lr | 0.876 | 0.842 | 0.388 | 0.837 | 0.385 | 0.266 |
| HistGBDT_moderate_depth | 0.828 | 0.815 | 0.421 | 0.811 | 0.416 | 0.288 |
| RF_shallow_sqrt_features | 0.750 | 0.733 | 0.506 | 0.730 | 0.496 | 0.347 |

**Reading scale:** **`RMSE`** and **`MAE`** are evaluated on **`log(price)`**.

**Structural story:** Shallower constrained RF materially under-fit relative to both deeper ensembles. **Deep RF** dominates validation and test. Aggressive HistGB tracks closely but retains **meaningful validation slack** (**≈0.004 R²**) and modestly higher **validation RMSE** vs champion RF despite faster early-stopping internals.

---

## 6. Why the winning model was selected

Selection rule spelled in training README / memo appendix: **`argmax`** validation **`R²`**, tie-break **`argmin`** validation **`RMSE`**.

**Winner:** **`RF_deeper_frac_features`** (RandomForestRegressor: **many trees**, unrestricted depth by default tuning in spec, fractional **`max_features=0.45`**, moderated leaf-split heuristics as coded in trainer).

**Operational justification for the team:**

- **Validation superiority** aligns with stakeholder risk — we avoid selecting on test leakage.
- **Generalization coherence:** uplift vs boosted specs reproduces directionally **on hold-out test**.
- Deep RF ensembles historically shine on **tabular mixed-type + wide one-hot exposures** reminiscent of heterogeneous STR micro-markets; gradient boosting sibling specs still competitive but statistically **inferior along the mandated selector**.

**(Caveat:** Training **`R² ≈ 0.957`** is **partially optimistic in-sample optimism** versus validation — expected with flexible forests — which is precisely why retention decisions rely **only** on validation stress.)

---

## 7. Key pricing drivers

We synthesize **two diagnostics** anchored to champion RF outputs:

### A. Native aggregated RF importances (collapsed one-hot exposures)

Dominant uplift mass concentrates in:

| Rank-space band | Signals (conceptual clustering) |
|-----------------|--------------------------------|
| Structural capacity | **`accommodates`**, **`bathrooms`**, **`bedrooms`**, **`beds`**, nuanced **`bathrooms_text`** |
| Geo layering | **`longitude`**, **`latitude`**, **`neighbourhood_cleansed`**, **`neighbourhood_group_cleansed`**, **`City`** |
| Listing archetyping | **`room_type`**, **`property_type`** |
| Operator footprints | **`host_total_listings_count`**, **`host_listings_count`**, calculated host decomposition columns (especially **private-room share signals**) |
| Policy surface | aggregates like **`minimum_maximum_nights`**, **`minimum_nights_avg_ntm`**, **`minimum_nights`**, **`maximum_nights_avg_ntm`** |
| Soft presentation | **`amenity_count`**, **`name_char_count`**, **`host_tenure_years`** |
| Spotlight binary | **`pool`** surfaces in splitter mass after capacity / geo arcs |

**(Exact ranking table exported:** `feature_importance_native_aggregated.csv`).**

### B. Validation permutation importance (shuffle penalty to `R²`)

Highest marginal dependencies (approximate permutation mean drop in **`R²`**, higher = harder to perturb safely):

| Feature | Permutation mean | Notes |
|---------|-----------------|-------|
| `accommodates` | ~0.117 | Clear #1 wedge |
| `longitude` | ~0.103 | Strong micro-market curvature |
| `host_total_listings_count` | ~0.082 | Operator scale wedge |
| `bathrooms` | ~0.074 | Bathrooms stack |
| `room_type` | ~0.071 | Product architecture |
| `latitude` | ~0.065 | Latitude complement |

Downstream materially important strata include **`bedrooms`**, **`neighbourhood_group_cleansed`**, **`minimum_maximum_nights`**, **`property_type`**, **`bathrooms_text`**, **`host_listings_count`**, **`minimum_nights_avg_ntm`**, private-room-calculus columns, **`neighbourhood_cleansed`**, **`City`**, **`amenity_count`**, **`host_tenure_years`**, and **`pool`**.

Full table: **`feature_importance_permutation_validation.csv`** (includes standard deviations per shuffle trials).

---

## 8. Market-level differences across cities

Modeling ingest embeds **`City`** plus granular geo — but **descriptive strata** illuminate **commercial heterogeneity**:

### Absolute price intensity (EDA cohort **post structural filters**, pre-occupancy-guard analytic count **103,592**)

From `eda/summary_logprice_by_city.csv` (mean log(price)):

| City | Count (EDA slice) | Mean log(price) | Median log(price) |
|------|-------------------|-----------------|-------------------|
| Hawaii | 33,113 | ~5.63 | ~5.45 |
| San Francisco | 5,793 | ~5.20 | ~5.14 |
| New York | 21,313 | ~5.13 | ~5.04 |
| Los Angeles | 36,750 | ~5.12 | ~5.04 |
| Nashville | 6,623 | ~5.11 | ~5.06 |

**(These directional facts inform positioning conversations; modeled champion already internalizes **`City`** + lat/lon interplay.)**

### Entire-home vs private-room dispersion (EDA table)

Delta mean log(price): Entire home/apt minus Private room (`eda/summary_city_entire_minus_private_gap.csv`):

| City | Δ mean log(price) |
|------|-------------------|
| Los Angeles | **1.0607** |
| Nashville | **0.8475** |
| New York | **0.8099** |
| San Francisco | **0.7545** |
| Hawaii | **0.2109** |

**Interpretation for team briefing:** Rough multiplicative magnification via **`exp(Δ)`** suggests **dramatically different uplift structures** LA vs constrained Hawaii deltas — underwriting cannot treat **national entire-home uplift** coefficients as transferable without **City-conditioned segmentation**. This directly corroborates **model design** emphasis on **`City`** + **`room_type`** interactions inside tree partitions.

---

## 9. Amenity findings

**Engineering fidelity** (`amenities_parse_distribution.txt` baseline on master before guard):

- Strict JSON-array parse reliability **≈99.97 %** (**34 malformed rows flagged** downstream with zeroed amenity count per dataset build safeguards).
- **Amenity token count distribution** median **≈38** amenities / listing (successful parses).

**Predictive uplift ordering (permutation view on champion RF):**

- **`amenity_count`** registers measurable lift (permutation mean drop in validation R² ≈ **1.27×10⁻²** upon shuffling) beyond single luxury flags — overall amenization / listing completeness acts as a broad quality proxy.
- **`pool`** dominates among **standalone engineered amenity binaries** (**≈1.12e-2** penalty magnitude), coherent with capex-heavy vacation inventory thesis.
- **Secondary tier** (hot tub, kitchen, workspace, washers, dryers, HVAC, self check-in) shows smaller but non-zero perturbation penalties (e.g. hot tub permutation mean ~4.6e-3 — see permutation CSV tail).
- **`wifi` permutation signal near negligible** (**~3.5e-5**) — unsurprising saturation / table-stakes framing.

Investor implication: Amenities reshape **pricing tail probabilities** conditional on geography + capacity—they **cannot replace** underwriting **bedrooms and bathroom stack** realism.

---

## 10. Investor implications (operational playbook)

| Theme | Actionable lens |
|----------|---------------------|
| **Capacity first** | ADR comps must align **sleeps/legal guest counts** (`accommodates`, bed/baths) prior to debating finishes. Mis-sized inventory mis-prices underwriting IRR. |
| **Geo fidelity** | **Lat/lon + neighborhoods** outperform headline city comps—local regulatory pockets and coastlines matter; treat **metro averages** skeptically when underwriting micro-clusters. |
| **Product taxonomy** | **Room modes** (`room_type`) + **supply archetypes** (`property_type`) reposition **risk / ADR ladders** materially—segment portfolios before benchmarking. |
| **Operator phenotype** | **Host listing counts / private-room footprints** correlate with differentiated pricing regimes—difference between **solo host** versus **semi-institutional aggregator** comps. |
| **Policy overlays** | **Minimum / maximum-night constraints** materially shift comparability—investigate calendar velocity externally to this nightly-only model before assuming ADR uplift sticks. |
| **Amenity ROI** | **Rich amenization** + **luxury cues (pool)** nudge valuations **after fundamentals** validated—capital plans should reconcile modeled uplift envelopes with **localized renovation cost curves**. |

All bullet guidance is **scenario planning**, **not audited appraisal.**

---

## 11. Important limitations and caution on interpretation

1. **Associative—not causal.** Importances & permutation deltas describe **dependence in scrape cross-section**. Renovation ROI or regulatory interventions require designs outside this sprint.
2. **Observed advertised price vs realized ADR.** Listings exhibit **strategy / discounting behaviors** unseen at snapshot—model explains **posted nightly ask**, **not negotiated realized clearing price**.
3. **Survivorship / platform selection.** Scraped inventories exclude delisted banned / pulled supply—potential **silent trimming** biases high-ADR survivorship narratives.
4. **Temporal alignment confounds.** Consolidated scrape batches align **deterministically** with **`City`** historically—interpret slow-changing macro shifts cautiously absent time-series augmentation.
5. **Review / reputation omitted by design.** Excluding review blocks avoids **feedback contamination** yet **drops demand-side reputation capital** latent in comps.
6. **Heavy-tail dollar noise.** Modeling uses **`log`** stabilization; translating back to nominal dollars nonlinearly exaggerates extremes—communicate **`log`** band uncertainty internally before client dollar narratives.
7. **Single champion snapshot.** Specifications tuned lightly for compute tractability—not exhaustive AutoML exhaustive sweep.

---

## 12. Link to broader project logic: revenue = price × occupancy × horizon

**Conceptual decomposition (business accounting):**

> **Annual (or lifecycle) lodging cash potential** aligns heuristically with **(nightly achievable rate) × (expected booked nights)** over the operating window — shorthand **≈ **`price`** × **`occupancy / utilization intensity`** × **`365`**-or-horizon-scaled calendar**.

Upstream documentation notes **`estimated_revenue_l365d` ≡ `price × estimated_occupancy_l365d` mechanically** inside master — tautology motivates **explicit modeling exclusion**.

**Pricing block stance:** Explain **ADR positioning levers.** **Separate occupancy strand** intentionally cordoned (**calendar / proxies absent from **`X`**) pending dedicated utilization modeling respecting **supply-demand feedback loops**.

Integration guidance for consolidated narrative:

| Module | Addresses | Leaves for sibling work |
|--------|-----------|-------------------------|
| **This block** | Structure of **posted nightly `price`** conditioned on lawful listing attributes | **Book nights realized**, churn, elasticity |
| Occupancy strand (future extension) | **Calendar intensity / proxies** respecting non-leakaged target definitions | Pricing ↔ utilization joint equilibrium cautions |

**Team alignment sentence:** Winning RF explains **cross-sectionally where ADR concentrates** consistent with comps logic; bridging to **PnL underwriting** demands multiplying those ADR contours by **forecast booked nights**, not multiplying **inside-model** by scraped occupancy substitutes already tied mechanically to **`price`** in raw master.

---

## Appendix: Key file pointers (no overwrites committed here)

| Purpose | Relative path |
|---------|---------------|
| Champion metrics & tables | `modeling/training_outputs_property_pricing/model_comparison_table.csv` |
| Stratified split counts | `modeling/training_outputs_property_pricing/data_split_sizes.csv` |
| Winner native importances | `modeling/training_outputs_property_pricing/feature_importance_native_aggregated.csv` |
| Winner permutation ranking | `modeling/training_outputs_property_pricing/feature_importance_permutation_validation.csv` |
| Earlier training synopsis (unchanged) | `modeling/training_outputs_property_pricing/memo_interpretation_property_pricing.txt` |
| Modeling dataset lineage | `modeling/property_pricing_dataset_preparation_summary.txt` |
| EDA synopsis | `eda/property_pricing_eda_summary.txt` |
| Trainers | `scripts/train_property_pricing_rf_vs_boost.py`, `scripts/build_property_pricing_modeling_dataset.py` |

---

*Prepared for internal coordination. External client wording should pass compliance / disclosure review.*
