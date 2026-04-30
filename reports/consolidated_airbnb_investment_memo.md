# Airbnb Investment Analytics Memo

## Executive Summary

This project evaluates where and how a client with a **$500,000 real estate acquisition budget** should invest in an Airbnb property across five candidate markets: **Hawaii, Los Angeles, New York, Nashville, and San Francisco**. The analysis moves from broad market screening to neighborhood and segment discovery, then to pricing drivers, guest experience signals, and finally to an actionable investment decision.

The central business equation is:

`Expected Annual Revenue = Nightly Price x Occupancy Rate x 365`

Every section of the project contributes to one part of that equation. The market analysis compares cities on revenue, occupancy, risk, saturation, and seasonality. The segmentation analysis identifies distinct listing archetypes and supply-demand gaps. The pricing model explains what drives nightly price. The guest experience analysis identifies what drives ratings and review language. The investment decision section combines those ideas with budget constraints, comparable-property validation, scenario analysis, and portfolio diversification.

At the broad market level, **Hawaii** is the strongest city on risk-adjusted revenue and typical revenue. It has the highest median annual revenue per listing and ranks first on the robust median/IQR revenue metric. However, Hawaii is also the most saturated market in the dataset, with very dense Airbnb supply and a high share of listings controlled by multi-listing hosts. That creates a strategic tension: Hawaii looks attractive at the market level, but it requires careful segment selection and competition-aware execution.

At the final investment-decision level, after applying **$500,000 budget feasibility rules**, the best single-property recommendation shifts to **Los Angeles / Hollywood Hills West / Entire home / 2 bedrooms**. This is because the Airbnb dataset does not contain purchase prices, so the budget had to be converted into realistic city-specific property configurations using external housing-price research. Under those feasibility rules, the Hollywood Hills West 2BR entire-home segment has the strongest revenue profile among decision-ready candidates and is validated by close comparable listings.

The final recommendation is:

- **Single-property strategy:** buy a **2-bedroom entire home in Hollywood Hills West, Los Angeles**.
- **Two-property strategy:** diversify with **Hollywood Hills West 2BR entire home + Midtown New York studio entire rental unit**.

The two-property portfolio keeps nearly the same expected revenue as the highest-revenue concentrated Los Angeles pair while reducing portfolio risk materially through geographic and product-type diversification.

## Data Foundation And Project Logic

The project relies on cleaned Airbnb listing, calendar, and review data. The main merged listing-level file is:

- `data/processed/master_data.csv`

This file contains listing attributes, city, price, property type, room type, bedrooms, review scores, occupancy proxies, and annualized operating fields. For time-based seasonality, the analysis uses the day-level calendar file:

- `data/processed/calendar_all_cleaned.csv`

The review and guest-experience work uses cleaned review text and joins it back to listing IDs in the master data. Across the project, the team treats Airbnb revenue as a function of three linked ideas:

1. **Price:** what the listing can charge per night.
2. **Occupancy:** how often it is likely to be booked.
3. **Risk and execution:** how stable, competitive, and operationally reliable the opportunity is.

This structure matters because a high nightly price alone is not enough. A listing with strong price but weak occupancy may underperform. Similarly, a high-revenue market may be unattractive if it is too saturated, too seasonal, or too exposed to regulation. The project therefore uses both statistical evidence and business constraints.

## Market-Level Screening

The first analytical block asks which city deserves the strongest initial attention. The market-level analysis answers four questions: which city has the best risk-adjusted revenue opportunity, how price and occupancy compare across cities, which markets are saturated, and how seasonality affects revenue.

The risk-adjusted revenue analysis uses a per-listing annual revenue proxy:

`estimated annual revenue = price x occupancy_rate_proxy x 365`

Because revenue distributions are heavily skewed, especially in Hawaii where luxury villas create extreme outliers, the project emphasizes a robust risk-adjusted metric:

`median revenue / revenue IQR`

Using that metric, **Hawaii ranks first**. Hawaii has a median annual revenue of about **$26,582**, the highest among the five cities, and a median/IQR risk-adjusted score of **0.562**. Nashville ranks second on risk-adjusted revenue, but its absolute revenue level is much lower. San Francisco has strong occupancy, New York has stable demand, and Los Angeles has the weakest risk-adjusted city-level profile in this market screen.

The price-occupancy-revenue comparison reinforces the Hawaii story. Hawaii has the highest median nightly price at about **$233**, while San Francisco has the highest typical occupancy. Hawaii also has the highest median annual revenue. New York has a high mean revenue, but that mean is heavily influenced by a small number of high-priced listings, making the median a more reliable measure of typical performance.

The saturation analysis complicates the Hawaii result. Hawaii is the most saturated market in the sample. It has the highest listings per 10,000 residents and a large share of supply in multi-listing host portfolios. In business terms, Hawaii is attractive but crowded. A new entrant cannot simply buy an average property and expect the market to carry them. They need a defensible segment, strong product quality, and careful operating execution.

Seasonality adds another risk dimension. Nashville has the strongest seasonality, with the largest revenue coefficient of variation and a peak-to-low revenue ratio of almost three times. New York is the most stable market, with the lowest revenue seasonality. Hawaii is moderately seasonal, with a clear autumn peak but not the extreme volatility seen in Nashville.

The market-level conclusion is therefore not “Hawaii is automatically the final answer.” The conclusion is more nuanced: **Hawaii is the strongest city-level prior, but it is also saturated, so downstream analysis must determine whether a specific segment and neighborhood can overcome that competition.**

**Statistical methods used in this section.** The market screen uses **descriptive statistics** by city, a **robust risk-adjusted revenue ratio** based on median/IQR, **distributional comparison** using boxplots, a **min-max scaled composite saturation index**, and **time-series aggregation** from daily calendar rows into monthly demand and revenue proxies. Q4 also uses the **coefficient of variation** to compare seasonality strength across cities.

**Additional numeric anchors.** Hawaii has about **33,132 active listings**, a **median nightly price of $233**, **median occupancy of 31.0%**, and **median annual revenue of $26,582**. San Francisco has the highest mean occupancy at roughly **39.0%**, while New York is the most stable seasonal market with revenue CV around **0.13**. Hawaii’s saturation score is **0.705**, driven by about **228 listings per 10,000 residents** and roughly **82.3%** of listings in multi-listing host portfolios. Nashville is the most seasonal market, with a revenue peak-to-low ratio of about **2.82x**.

**Figures that fit naturally in this body.** When turning this memo into a report, include `reports/figures/market_analysis/q1_risk_adjusted_revenue/03_q1_return_vs_risk.png` after the risk-adjusted revenue discussion, because it visually shows the return-risk tradeoff. Include `reports/figures/market_analysis/q3_market_saturation/03_q3_saturation_score.png` after the saturation paragraph. Include `reports/figures/market_analysis/q4_seasonality/03_q4_seasonality_strength.png` after the seasonality paragraph. If space allows, `reports/figures/market_analysis/q2_price_occupancy_revenue/03_q2_three_metric_comparison.png` is the best single chart for price, occupancy, and revenue side by side.

Useful supporting outputs:

- `results/01_market_analysis/market_analysis_memo.md`
- `reports/figures/market_analysis/q1_risk_adjusted_revenue/03_q1_return_vs_risk.png`
- `reports/figures/market_analysis/q3_market_saturation/03_q3_saturation_score.png`
- `reports/figures/market_analysis/q4_seasonality/03_q4_seasonality_strength.png`

## Segmentation And Neighborhood Strategy

The segmentation block moves from city-level screening into market structure. It uses **K-Means clustering** to group listings into business-relevant segments based on listing characteristics such as price, occupancy, accommodates, bedrooms, bathrooms, and minimum-night policy.

The final segmentation model uses **six clusters**. The team considered elbow and silhouette evidence, but chose a business-interpretable number of clusters rather than the purely mechanical minimum. The resulting clusters include:

- Long-stay focused listings
- Budget high-occupancy studios
- General mid-tier listings
- Premium mid-size active listings
- Premium mid-size slow-turn listings
- Luxury large homes

This segmentation helps explain that not all Airbnb supply competes in the same way. A luxury large home and a budget studio are different businesses, even if both appear in the same city. Segmentation therefore provides language for the investment discussion: the client should not just choose a city, but a segment within a city.

Inside Hawaii, the segmentation analysis identifies **Ewa, Koloa-Poipu, and Lihue** as standout neighborhoods. Ewa ranks especially well because it combines high revenue, high occupancy, and a balanced price-occupancy relationship. Lihue and North Kona show negative premium gaps, meaning demand appears strong relative to price, which may suggest pricing headroom.

The segmentation analysis also identifies risk. Hawaii’s **General mid-tier** cluster is oversupplied: it represents a large share of supply but has low occupancy. That segment should be avoided. In contrast, luxury large homes and some premium mid-size segments appear more underserved, meaning they have relatively stronger demand compared with their supply share.

This block is important because it prevents the investment recommendation from being too broad. The market analysis says Hawaii is attractive, but segmentation says the attractive opportunity is not “any Hawaii Airbnb.” It is specific neighborhoods and specific segments, while avoiding oversupplied mid-tier inventory.

**Statistical methods used in this section.** The segmentation block uses **K-Means clustering** on standardized listing-level features, with **elbow and silhouette analysis** to evaluate possible values of k. The team selected **k = 6** as the best business-interpretable segmentation structure. The neighborhood ranking then uses **z-score normalization** and a weighted composite score: revenue receives the largest weight, followed by occupancy and price. The supply-demand gap analysis compares each segment’s **supply share** with its **median occupancy** to classify segments as hot, underserved, oversupplied, or cold/thin.

**Additional numeric anchors.** The segmentation model covers about **102,909 cleaned listings**. The six clusters include a **Luxury large home** segment with median annual revenue proxy around **$102,393**, a **Premium mid-size active** segment with median price around **$312** and median occupancy around **34.8%**, and a **Budget high-occupancy studio** segment with median occupancy around **76.2%**. In Hawaii, **Ewa** ranks first among neighborhoods with about **827 listings**, median price around **$461**, median occupancy around **47.7%**, and median revenue around **$62,092**. **Koloa-Poipu** and **Lihue** follow. Hawaii’s **General mid-tier** segment represents about **35.3%** of Hawaii supply but only about **20.3%** median occupancy, which is why it is treated as oversupplied.

**Figures that fit naturally in this body.** Include `reports/figures/02_segmentation/01_elbow_silhouette.png` near the paragraph explaining the choice of six clusters. Use `reports/figures/02_segmentation/03_cluster_profile_heatmap.png` to show how the clusters differ across features. Use `reports/figures/02_segmentation/04_neighborhood_ranking_hawaii.png` after the Hawaii neighborhood paragraph. Use `reports/figures/02_segmentation/05_supply_demand_gap.png` after the oversupply/undersupply discussion.

Useful supporting outputs:

- `results/02_segmentation/segmentation_memo.md`
- `reports/figures/02_segmentation/01_elbow_silhouette.png`
- `reports/figures/02_segmentation/03_cluster_profile_heatmap.png`
- `reports/figures/02_segmentation/04_neighborhood_ranking_hawaii.png`
- `reports/figures/02_segmentation/05_supply_demand_gap.png`

## Pricing Model And Price Drivers

The pricing block asks what observable features explain nightly advertised price. This is a supervised learning section focused on predicting **log(price)**. The model is not designed to estimate causal renovation ROI. Instead, it acts as a comps-intelligence tool: it identifies which listing traits co-move most strongly with price across the Airbnb dataset.

The team compared Random Forest and gradient-boosted tree specifications. The preferred model is:

**RF_deeper_frac_features**

It achieved approximately:

- Validation R²: **0.846**
- Validation RMSE: **0.384 log-units**
- Test R²: **0.839**
- Test RMSE: **0.384**

The model was selected using validation performance, not test performance. This preserves a clean modeling logic and reduces the risk of selecting a model because it happened to perform well on one test split.

The pricing model’s strongest drivers are commercially intuitive. The top drivers include:

- Guest capacity, especially `accommodates`
- Location, including latitude, longitude, city, and neighborhood
- Bathrooms and bedrooms
- Room type and property type
- Host portfolio scale
- Minimum and maximum-night policy fields
- Amenity count and pool

The business interpretation is that price is not driven by one magic amenity. It is driven first by capacity, geography, and product type, then refined by operator and amenity signals. Amenities such as pools matter, but they matter after the fundamentals of location and capacity are already comparable.

The pricing optimization memo also examines how price, estimated annual occupancy, and annual revenue proxy relate descriptively. It shows a weak negative relationship between price and estimated occupancy, which is expected: more expensive properties often book fewer nights. However, the high-price tertile still has higher mean annual revenue because the nightly rates are much larger. This is not causal elasticity. It does not prove that raising price increases revenue. Instead, it shows that different listing types occupy different points in the price-occupancy tradeoff.

This matters for the final recommendation because it warns against oversimplified pricing logic. The client should not simply seek the highest nightly rate. They should seek a feasible property type with validated comparable revenue, realistic occupancy, and a manageable risk profile.

**Statistical methods used in this section.** The pricing block uses **supervised learning** to predict `log(price)`. The team compared **Random Forest** and **Histogram Gradient Boosting** models using a train/validation/test structure. The preferred model was selected by **validation R²** and checked on the held-out test set. Interpretation uses **permutation feature importance**, which measures how much validation R² falls when each feature is shuffled. The pricing optimization subsection uses **Pearson correlations**, **equal-count price tertiles**, and descriptive summaries by city and room type.

**Additional numeric anchors.** The modeling cohort has about **103,500 listings** after quality filters. The winning Random Forest model has **validation R² about 0.846** and **test R² about 0.839**. Its most important features include `accommodates` with permutation drop around **0.117**, `longitude` around **0.103**, `host_total_listings_count` around **0.082**, `bathrooms` around **0.074**, and `room_type` around **0.071**. In the descriptive pricing analysis, the global high-price tertile has mean nightly price around **$1,540**, mean estimated occupancy around **51 nights/year**, and mean annual revenue proxy around **$27,189**. The correlation between price and estimated occupancy is weakly negative at about **-0.086**, while price and revenue proxy are weakly positive at about **0.188**.

**Figures that fit naturally in this body.** Include `results/03_pricing_models/pricing_final_feature_importance_figure.png` after the model-driver paragraph. Include `results/03_pricing_models/pricing_final_city_comparison_figure.png` after the city heterogeneity discussion. Include `results/03_pricing_models/pricing_final_price_band_figure.png` after the price-band paragraph because it directly shows the price-occupancy-revenue tradeoff.

Useful supporting outputs:

- `results/03_pricing_models/pricing_final_integrated_memo.md`
- `results/03_pricing_models/model_comparison_table.csv`
- `results/03_pricing_models/feature_importance_permutation_validation.csv`
- `results/03_pricing_models/pricing_final_feature_importance_figure.png`
- `results/03_pricing_models/pricing_final_price_band_figure.png`

## Guest Experience And Text Analytics

The guest-experience block adds the customer and operations perspective. Revenue is not only about property attributes; it also depends on whether guests have experiences that support high ratings, repeat demand, and strong review language.

This block uses cleaned review text and listing-level review scores. It combines several methods:

- Regex-based complaint cue detection
- TF-IDF text mining at listing and city levels
- Logistic regression and Random Forest classification for high overall ratings
- Amenity and operations proxy analysis
- Top-performer language lift

The complaint analysis finds that **Hawaii** has the highest share of reviews containing problem-oriented language, at about **20.1%**. New York, San Francisco, Nashville, and Los Angeles follow. This does not automatically mean Hawaii is operationally worse; it may reflect guest expectations, property mix, or segment composition. But it is a warning that high-revenue markets also require strong operational control.

The high-rating model identifies **cleanliness** and **communication** as the strongest predictors of achieving an overall rating of at least 4.9. Cleanliness has the highest Random Forest feature importance, and communication ranks second. Check-in and location matter as well, but less strongly in this model.

Operational proxy analysis suggests that lockbox, keypad, smart-lock, and cleaning-related amenity language are associated with higher average ratings. Instant Book appears lower in this snapshot, but the memo correctly treats that as likely segment mix rather than proof that Instant Book causes worse reviews.

The top-performer language analysis shows that high-rated listings over-index on endorsement and repeat-stay terms, such as recommend, again, friendly, experience, and back. This suggests that top listings do not only avoid complaints; they create an experience guests want to repeat and recommend.

The investment implication is straightforward: once a property segment is selected, operational execution matters. In a competitive market, the client should invest in professional cleaning, responsive communication, arrival simplicity, and review-driven messaging. These are not just “nice to have” features; they are tied to the review outcomes that support pricing power and occupancy.

**Statistical methods used in this section.** The guest-experience block combines **regular-expression text classification**, **TF-IDF text mining**, **logistic regression**, **Random Forest classification**, and **term-lift analysis**. Complaint cues are identified with regex patterns over cleaned review text. TF-IDF is computed at listing and city levels to find distinctive review language. The high-rating model predicts whether a listing has overall rating at least **4.9** using structured review sub-scores. Top-performer language is measured using lift between top-quartile listings and the rest.

**Additional numeric anchors.** The complaint-cue analysis scans more than **4.4 million in-scope reviews** across the five cities. Hawaii has the highest complaint-cue share at about **20.1%**, followed by New York at about **17.6%**, San Francisco at about **16.0%**, Nashville at about **15.6%**, and Los Angeles at about **15.1%**. In the high-rating model, cleanliness has Random Forest importance around **0.43**, communication around **0.26**, check-in around **0.17**, and location around **0.14**. Logistic regression test AUC is about **0.91**, showing that these sub-scores strongly predict high overall ratings. Lockbox/keypad/smart-lock language is associated with mean overall rating around **4.23**, and cleaning-related amenity language around **4.15**.

**Figures that fit naturally in this body.** Include `reports/figures/04_guest_experience/q1_complaint_cue_rate_by_city.png` after the complaint paragraph. Include `reports/figures/04_guest_experience/q2_subscore_drivers_rf_logistic.png` after the high-rating model paragraph. Include `reports/figures/04_guest_experience/q3_operational_signals_mean_rating.png` after the operational proxy paragraph. Include `reports/figures/04_guest_experience/q4_term_lift_top_performers.png` after the top-performer language paragraph.

Useful supporting outputs:

- `results/04_guest_experience/text_analytics_memo.md`
- `results/04_guest_experience/04_guest_experience.txt`
- `reports/figures/04_guest_experience/q1_complaint_cue_rate_by_city.png`
- `reports/figures/04_guest_experience/q2_subscore_drivers_rf_logistic.png`
- `reports/figures/04_guest_experience/q3_operational_signals_mean_rating.png`
- `reports/figures/04_guest_experience/q4_term_lift_top_performers.png`

## Investment Decision Model

The final block synthesizes the prior analysis into an actionable investment decision. This is where the project moves from describing the Airbnb market to recommending what the client should buy.

The most important constraint is the **$500,000 purchase budget**. The Airbnb dataset does not include property acquisition prices, so the team used external housing-price research to define what the budget realistically buys in each city. These constraints were translated into feasibility rules:

- Hawaii: studio to 1BR condo/apartment-style units
- New York: studio to 1BR in Manhattan; up to 2BR in outer boroughs
- San Francisco: studio to small 1BR
- Los Angeles: 1BR to 2BR condo/apartment-style units
- Nashville: 2BR to 4BR homes, townhouses, condos, or rental units

This is the reason the final recommendation can differ from the broad market-level Hawaii result. Hawaii may be the best city-level revenue market, but the client’s $500,000 budget limits what can actually be purchased there. Once the analysis filters for budget-feasible property configurations and ranks candidate segments, the strongest single-property segment becomes **Los Angeles / Hollywood Hills West / Entire home / 2 bedrooms**.

The candidate has:

- Comparable listings: **46**
- Median nightly price: **$376**
- Median occupancy proxy: **38.1%**
- Median annual revenue: **$47,628**
- Median review score: **4.95**
- k-NN comparable median annual revenue: **$47,640**

The k-nearest-neighbor validation is crucial. The recommendation is not based only on a grouped median. The closest comparable listings produce almost the same median revenue as the candidate segment, which supports the realism of the estimate.

Scenario analysis adds uncertainty. For the recommended Hollywood Hills West segment:

- Conservative revenue: **$20,100**
- Moderate revenue: **$47,628**
- Optimistic revenue: **$78,957**
- Bootstrap 90% confidence interval: **$37,638-$63,627**

The downside case is much lower than the moderate case, so the recommendation should not be presented as guaranteed income. It is a high-potential but execution-sensitive opportunity.

The risk analysis combines downside revenue risk, bootstrap uncertainty, seasonality, competition, scrape-date freshness, and regulatory proxy risk. Los Angeles has meaningful short-term rental compliance risk and a notable seasonality gap. Lower-risk alternatives such as Silver Lake and Hollywood Hills are credible, but Hollywood Hills West remains the best single-property revenue recommendation because it has the highest moderate revenue and the strongest k-NN validation.

For a two-property strategy, the analysis compares candidate pairs like a simple investment portfolio. The highest-revenue pair is concentrated in Los Angeles: Hollywood Hills West 2BR plus Hollywood Hills 2BR. It produces about **$93,220** in moderate combined annual revenue, but it has a high risk score and perfect city correlation.

The recommended diversified portfolio is:

**Hollywood Hills West 2BR entire home + Midtown New York studio entire rental unit**

This portfolio has:

- Moderate combined revenue: **$92,736**
- Conservative combined revenue: **$39,688**
- Optimistic combined revenue: **$156,605**
- Portfolio risk score: **0.24**
- City occupancy correlation: **0.29**
- Risk-adjusted revenue score: **$75,023**

The diversified portfolio gives up only about **$484** in moderate annual revenue compared with the maximum-revenue pair, while sharply reducing concentration risk. This makes it the better recommendation if the client can buy two properties.

**Statistical methods used in this section.** The investment block uses **constrained filtering**, **grouped descriptive statistics**, **k-nearest-neighbor comparable validation**, **scenario analysis**, **bootstrap resampling**, **normalized weighted risk scoring**, **correlation analysis**, and **portfolio optimization / efficient-frontier-style comparison**. The constrained filter translates external housing-price research into city-specific bedroom and property-type feasibility rules. Grouped statistics rank feasible segments by revenue, occupancy, reviews, and sample size. k-NN validates whether the selected segment is supported by similar individual listings. Bootstrap resampling estimates uncertainty around median revenue. The portfolio section treats candidate segments like assets and compares two-property combinations by revenue, risk, and city occupancy correlation.

**Additional numeric anchors.** The final decision-ready candidate universe contains **243 segments** after budget, sample-size, and review-score filters. The recommended Hollywood Hills West candidate has **46 comparable listings**, **$47,628** median annual revenue, **$376** median nightly price, **38.1%** median occupancy proxy, and **4.95** median review score. k-NN validation gives **$47,640** median revenue among closest comparable listings, only **$12** above the segment median. The risk score combines downside risk, bootstrap uncertainty, seasonality, competition, scrape-date freshness, and regulatory proxy risk. The diversified LA + NYC portfolio has **$92,736** moderate revenue and **0.24** risk score, compared with **$93,220** moderate revenue and **0.84** risk score for the max-revenue LA-only portfolio.

**Figures that fit naturally in this body.** Include `reports/figures/05_investment_decision/step1_top_candidate_revenue.png` after the single-property recommendation. Include `reports/figures/05_investment_decision/step2_knn_validation_comparison.png` after the k-NN paragraph. Include `reports/figures/05_investment_decision/step3_revenue_scenarios.png` and `reports/figures/05_investment_decision/step4_risk_components_heatmap.png` in the scenario/risk discussion. Include `reports/figures/05_investment_decision/step5_portfolio_revenue_vs_risk.png` and `reports/figures/05_investment_decision/step5b_efficient_frontier.png` in the portfolio recommendation.

Useful supporting outputs:

- `reports/investment_decision/final_investment_decision_section.md`
- `reports/figures/05_investment_decision/step1_top_candidate_revenue.png`
- `reports/figures/05_investment_decision/step2_knn_validation_comparison.png`
- `reports/figures/05_investment_decision/step3_revenue_scenarios.png`
- `reports/figures/05_investment_decision/step4_risk_components_heatmap.png`
- `reports/figures/05_investment_decision/step5_portfolio_revenue_vs_risk.png`
- `reports/figures/05_investment_decision/step5b_efficient_frontier.png`

## Integrated Recommendation

The project’s logic can be summarized as a narrowing funnel.

First, the market analysis identifies Hawaii as the strongest broad market on risk-adjusted revenue, while warning that Hawaii is highly saturated. Second, segmentation explains that the opportunity is not the average Hawaii listing, but specific neighborhoods and segments. Third, the pricing model shows that price is driven by capacity, geography, room type, property type, host scale, and amenities, which means underwriting must be local and segment-specific. Fourth, guest experience analysis shows that cleanliness, communication, and arrival experience are key operational levers for ratings and repeat demand.

Finally, the investment decision layer adds the client’s $500,000 constraint. Under that constraint, the best single-property recommendation is not the broad Hawaii market. It is **Hollywood Hills West, Los Angeles, 2-bedroom entire home**, because it is budget-feasible, revenue-attractive, and validated by close comparables.

The final recommendation is therefore:

1. **Buy one property:** target a **2-bedroom entire home in Hollywood Hills West, Los Angeles**.
2. **If buying two properties:** pair that Los Angeles asset with a **Midtown New York studio entire rental unit** to reduce concentration risk.
3. **Operate deliberately:** prioritize professional cleaning, fast communication, smooth check-in, and strong guest-experience messaging.
4. **Do legal due diligence:** Los Angeles and New York both require serious short-term-rental compliance checks before acquisition.

This recommendation is data-driven but not risk-free. The analysis estimates revenue potential, not net profit. It does not include acquisition price at the property level, financing, taxes, insurance, HOA fees, cleaning fees, maintenance, management costs, or regulatory approval costs. Those items must be modeled before a real acquisition decision.

## Limitations And Due Diligence

Several limitations should frame how the client uses this memo.

First, Airbnb data reflects platform listings, not the full real estate market. The dataset does not include actual purchase prices, which is why the investment section uses external housing research to define budget-feasible property configurations.

Second, many revenue fields are proxies. The project uses price, occupancy proxy, estimated occupancy, and estimated annual revenue fields depending on the analytical question. These are useful for comparing markets and segments, but they are not audited profit-and-loss statements.

Third, predictive models are associative. The Random Forest pricing model explains listed nightly prices, but it does not prove that adding an amenity or changing a policy will causally increase revenue. Similarly, guest-experience signals show associations with ratings, not guaranteed ROI.

Fourth, regulation is treated as a proxy risk. Cities such as New York, San Francisco, Los Angeles, and Hawaii require legal due diligence that goes beyond the Airbnb dataset.

Fifth, the final recommendation is gross-revenue focused. A real investor should build a net operating income model that includes purchase cost, mortgage terms, tax treatment, insurance, cleaning, repairs, professional management, platform fees, vacancy, and local permit requirements.

## Appendix: Core Artifacts

Market analysis:

- `results/01_market_analysis/market_analysis_memo.md`
- `results/01_market_analysis/q1_risk_adjusted_revenue/q1_summary.md`
- `results/01_market_analysis/q2_price_occupancy_revenue/q2_summary.md`
- `results/01_market_analysis/q3_market_saturation/q3_summary.md`
- `results/01_market_analysis/q4_seasonality/q4_summary.md`

Segmentation:

- `results/02_segmentation/segmentation_memo.md`
- `results/02_segmentation/segmentation_summary.md`

Pricing:

- `results/03_pricing_models/pricing_final_integrated_memo.md`
- `results/03_pricing_models/model_comparison_table.csv`
- `results/03_pricing_models/feature_importance_permutation_validation.csv`

Guest experience:

- `results/04_guest_experience/text_analytics_memo.md`
- `results/04_guest_experience/04_guest_experience.txt`
- `results/04_guest_experience/q1_review_complaints/q1_summary.md`
- `results/04_guest_experience/q2_five_star_drivers/q2_summary.md`
- `results/04_guest_experience/q3_operational_investments/q3_summary.md`
- `results/04_guest_experience/q4_top_performer_praise/q4_summary.md`

Investment decision:

- `reports/investment_decision/final_investment_decision_section.md`
- `reports/investment_decision/step1_budget_feasible_candidates.md`
- `reports/investment_decision/step2_knn_comparable_validation.md`
- `reports/investment_decision/step3_bootstrap_scenarios.md`
- `reports/investment_decision/step4_risk_decomposition.md`
- `reports/investment_decision/step5_portfolio_diversification.md`
- `reports/investment_decision/step5b_efficient_frontier.md`
