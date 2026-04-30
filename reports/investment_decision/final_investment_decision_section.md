# Final Investment Decision Section

## Executive Recommendation

The strongest single-property recommendation after switching to the merged master dataset is:

**Los Angeles / Hollywood Hills West / Entire home / 2 bedrooms**

This is the top budget-feasible candidate after applying the $500,000 affordability rules, master-data operating performance, k-nearest-neighbor validation, scenario analysis, bootstrap uncertainty, and risk decomposition.

The best risk-aware two-property portfolio is:

**Los Angeles / Hollywood Hills West / Entire home / 2BR + New York / Midtown / Entire rental unit / studio**

This portfolio is not the lowest-risk pair, but it is the best risk-adjusted diversified portfolio among the frontier candidates. It pairs the highest-revenue single-property candidate with a different city and property type, reducing concentration risk relative to buying two Los Angeles properties.

## Important Data Change

The investment section now uses:

`data/processed/master_data.csv`

This file already merges listing attributes with calendar-derived operating fields. Step 1 no longer reads separate listings and calendar files directly. Instead, it uses:

- `estimated_revenue_l365d` as the annual revenue source when available
- `estimated_occupancy_l365d` and `occupancy_rate_proxy` as calendar-derived occupancy measures
- listing `price` as a fallback when revenue/occupancy cannot infer a nightly rate
- listing attributes such as city, neighborhood, room type, property type, bedrooms, reviews, and ratings

The one important modeling split is now explicit: `master_data.csv` is listing-level and annualized, while `data/processed/calendars/calendar_all_cleaned.csv` contains the date-level calendar records needed for monthly seasonality. The investment economics use master data; the time-based risk analysis uses the combined calendar file. `calendar_last_scraped` is used as a freshness/snapshot-consistency check from master data, not as a seasonality variable.

## Core Investment Questions Answered

### 1. Given a $500,000 budget, what is the optimal property configuration and where?

The recommended single-property configuration is a **2-bedroom entire home in Hollywood Hills West, Los Angeles**.

Key operating metrics:

- Comparable listings in segment: `46`
- Median nightly price: `$376`
- Median occupancy proxy: `38.1%`
- Median annual revenue: `$47,628`
- Median review score: `4.95`
- k-NN comparable median annual revenue: `$47,640`
- Budget feasibility rule: Los Angeles can plausibly reach 1-2 bedroom condo/apartment-style units near the $500,000 budget range.

The key reason this candidate rises to the top is not just its segment median. Its k-NN comparable median is almost identical to the segment median, which means the recommendation is supported by similar real listings rather than only by a broad segment average.

### 2. What is the projected annual revenue under different scenarios?

For the recommended Hollywood Hills West 2BR entire home segment:

- Conservative scenario: `$20,100`
- Moderate scenario: `$47,628`
- Optimistic scenario: `$78,957`
- Bootstrap 90% confidence interval for median revenue: `$37,638-$63,627`
- k-NN comparable median revenue: `$47,640`

The conservative, moderate, and optimistic scenarios are based on the 25th percentile, median, and 75th percentile of the candidate segment. Bootstrap resampling estimates uncertainty around the segment median. k-NN validation checks whether nearby comparable listings support the segment result.

Business interpretation: the expected revenue is lower than the previous separate-calendar run because the new master-data source uses Airbnb's merged annual revenue estimate rather than the earlier separately computed calendar revenue. The recommendation is therefore more conservative and more consistent with the current master dataset.

### 3. What are the biggest risks to this investment?

For Hollywood Hills West 2BR entire homes, the main risks are:

- **Downside revenue risk:** conservative revenue is `$20,100`, meaning the lower-quartile outcome is less than half of the median.
- **Bootstrap uncertainty:** the 90% bootstrap interval is `$37,638-$63,627`, so the typical revenue estimate has meaningful but manageable uncertainty.
- **Seasonality risk:** Los Angeles has a `30.1%` peak-to-trough monthly occupancy gap based on the monthly calendar summary.
- **Regulatory risk:** Los Angeles has meaningful short-term-rental compliance risk and requires external legal due diligence.
- **Competition risk:** Hollywood Hills West has `94` budget-feasible comparable listings in the neighborhood universe used for risk scoring.

Risk-adjusted ranking among the evaluated top candidates:

1. **Los Angeles / Silver Lake / Entire home / 2BR**
   - moderate revenue: `$45,138`
   - overall risk score: `0.40`
   - risk-adjusted revenue score: `$32,202`

2. **Los Angeles / Hollywood Hills / Entire home / 2BR**
   - moderate revenue: `$45,592`
   - overall risk score: `0.42`
   - risk-adjusted revenue score: `$32,141`

3. **Los Angeles / Hollywood Hills West / Entire home / 2BR**
   - moderate revenue: `$47,628`
   - overall risk score: `0.67`
   - risk-adjusted revenue score: `$28,566`

Business interpretation: Hollywood Hills West remains the best single-property revenue recommendation because it has the highest moderate revenue and the strongest k-NN validation. However, Silver Lake and Hollywood Hills are credible lower-risk alternatives.

### 4. If the client could buy two properties instead of one, how should they diversify?

The highest-revenue two-property portfolio is:

**Hollywood Hills West 2BR entire home + Hollywood Hills 2BR entire home**

- Moderate combined annual revenue: `$93,220`
- Conservative combined annual revenue: `$41,712`
- Optimistic combined annual revenue: `$148,212`
- Portfolio risk score: `0.84`
- City occupancy correlation: `1.00`

This is the maximum-revenue option, but it is concentrated in Los Angeles and in the same property type.

The recommended diversified portfolio is:

**Hollywood Hills West 2BR entire home + Midtown NYC studio entire rental unit**

- Moderate combined annual revenue: `$92,736`
- Conservative combined annual revenue: `$39,688`
- Optimistic combined annual revenue: `$156,605`
- Portfolio risk score: `0.24`
- City occupancy correlation: `0.29`
- Risk-adjusted revenue score: `$75,023`

Business interpretation: this portfolio gives up only `$484` in moderate annual revenue compared with the max-revenue pair, but it cuts the risk score from `0.84` to `0.24`. That is a much better tradeoff for a client who cares about diversification and downside control.

## Method Summary

### Step 1: Budget-Feasible Candidate Universe

The analysis first translated the $500,000 budget into feasible property configurations by city:

- Hawaii: studio to 1BR condo/apartment-style units
- New York: studio to 1BR in Manhattan; up to 2BR in outer boroughs
- San Francisco: studio to small 1BR
- Los Angeles: 1BR to 2BR condo/apartment-style units
- Nashville: 2BR to 4BR homes, townhouses, condos, or rental units

Then it filtered Airbnb listings to:

- entire home/apartment listings only
- plausible residential property types
- nightly price between `$50` and `$1,500`
- occupancy proxy between `0%` and `100%`
- annual revenue between `$1,000` and `$250,000`
- decision-ready segments with at least `25` comparable listings
- median review score of at least `4.5`

Top candidate segments after the master-data refresh:

| Rank | Candidate | Median Revenue | Median Price | Median Occupancy | Comps |
|---:|---|---:|---:|---:|---:|
| 1 | Los Angeles / Hollywood Hills West / Entire home / 2BR | `$47,628` | `$376` | `38.1%` | `46` |
| 2 | Los Angeles / Hollywood Hills / Entire home / 2BR | `$45,592` | `$356` | `50.4%` | `52` |
| 3 | Los Angeles / Silver Lake / Entire home / 2BR | `$45,138` | `$251` | `51.0%` | `54` |
| 4 | New York / Midtown / Entire rental unit / studio | `$45,108` | `$252` | `49.6%` | `151` |
| 5 | Los Angeles / Manhattan Beach / Entire home / 2BR | `$43,968` | `$391` | `34.2%` | `26` |

### Step 2: k-NN Comparable Validation

k-NN is used as a realism check, not as the primary investment model. For each top segment, it finds similar real listings in the same city, neighborhood, property type, and bedroom count.

The recommended Hollywood Hills West segment is strongly validated:

- Segment median revenue: `$47,628`
- k-NN median revenue: `$47,640`
- validation gap: `$12`
- validation status: supported by close comps

This is important because several other high-ranking segments look weaker after k-NN validation:

- Hollywood Hills: k-NN median is `$7,612` below segment median
- Silver Lake: k-NN median is `$12,432` below segment median
- Midtown NYC: k-NN median is `$10,543` below segment median
- Manhattan Beach: k-NN median is `$22,908` below segment median

### Step 3: Scenario And Bootstrap Analysis

The scenario analysis creates conservative, moderate, and optimistic revenue estimates from the distribution of comparable listings. The bootstrap analysis resamples candidate listings to estimate uncertainty around the segment median.

For Hollywood Hills West:

- conservative revenue: `$20,100`
- moderate revenue: `$47,628`
- optimistic revenue: `$78,957`
- bootstrap mean median revenue: `$48,533`
- bootstrap 90% CI: `$37,638-$63,627`
- bootstrap CI width: `$25,989`

Business interpretation: the median case is credible, but the downside case is real. This should be presented as a high-potential but execution-sensitive investment rather than a guaranteed cash-flow result.

### Step 4: Risk Decomposition

The risk model combines:

- downside risk from the conservative-to-moderate revenue gap
- bootstrap uncertainty
- city-level seasonality from `calendar_all_cleaned.csv`
- neighborhood competition
- calendar scrape-date freshness from `calendar_last_scraped`
- regulatory proxy risk

The strongest business interpretation is that **Los Angeles dominates the top revenue candidates, but Los Angeles also carries meaningful regulatory and seasonality risk**. The recommendation is therefore not simply "buy the top revenue segment"; it is "buy the top segment only if the client accepts local compliance due diligence and active operating execution." The scrape-date check shows that cities are measured within tight one-day windows, with San Francisco observed on one scrape date, so freshness does not materially change the recommendation.

Lower-risk alternatives:

- Silver Lake 2BR entire home has slightly lower revenue but a better risk-adjusted score.
- Hollywood Hills 2BR entire home has similar revenue and a better risk-adjusted score than Hollywood Hills West.
- New York Midtown studio has high regulatory risk, so it is more useful as a diversification candidate than as the single-property recommendation.

### Step 5: Two-Property Portfolio Diversification

The portfolio model evaluates pairs of candidate segments using:

- combined conservative, moderate, and optimistic revenue
- city occupancy correlation
- same-city concentration
- same-neighborhood concentration
- same-property-type concentration
- average segment uncertainty
- average systematic and regulatory risk

Best portfolio types:

| Portfolio Type | Properties | Moderate Revenue | Risk Score | Interpretation |
|---|---|---:|---:|---|
| Max revenue | Hollywood Hills West + Hollywood Hills | `$93,220` | `0.84` | Highest revenue, but concentrated in LA |
| Diversified | Hollywood Hills West + Midtown NYC | `$92,736` | `0.24` | Best risk-adjusted diversified choice |
| Lower risk | Fort Hamilton NYC + Culver City LA | `$78,795` | `0.00` | Lowest risk, but materially lower revenue |

### Step 5B: Efficient Frontier

The efficient frontier confirms the tradeoff:

- Lowest-risk frontier portfolio: Fort Hamilton NYC studio + Culver City LA 2BR home
- Best risk-adjusted diversified portfolio: Hollywood Hills West LA 2BR home + Midtown NYC studio
- Max-revenue frontier portfolio: Hollywood Hills West LA 2BR home + Hollywood Hills LA 2BR home

The diversified LA + NYC portfolio is the best recommendation because it produces nearly the same moderate revenue as the max-revenue concentrated portfolio while materially lowering risk.

## Final Recommendation

### Single-Property Strategy

**Choose a 2-bedroom entire home in Hollywood Hills West, Los Angeles.**

Why:

- highest median annual revenue among decision-ready candidates
- strong sample size for this segment (`46` comparable listings)
- excellent review profile (`4.95` median review score)
- k-NN median revenue almost exactly matches the segment median
- feasible under the Los Angeles $500K property-size assumption

Main cautions:

- conservative revenue is much lower than median revenue
- Los Angeles has regulatory/compliance risk
- seasonality and execution quality matter
- the analysis estimates revenue, not net profit or ROI, because purchase prices, financing, tax, insurance, HOA, cleaning, and maintenance costs are not in the Airbnb dataset

### Two-Property Strategy

**Choose Hollywood Hills West 2BR entire home + Midtown NYC studio entire rental unit.**

Why:

- moderate combined revenue is `$92,736`
- revenue is almost the same as the max-revenue LA-only portfolio
- risk score is much lower than the max-revenue portfolio
- city correlation is only `0.29`, giving meaningful diversification
- the pair diversifies across both city and property type

This is the recommended two-property strategy because it balances revenue and diversification better than buying two Los Angeles properties.

## Files Supporting This Section

Markdown reports:

- `reports/investment_decision/step1_budget_feasible_candidates.md`
- `reports/investment_decision/step2_knn_comparable_validation.md`
- `reports/investment_decision/step3_bootstrap_scenarios.md`
- `reports/investment_decision/step4_risk_decomposition.md`
- `reports/investment_decision/step5_portfolio_diversification.md`
- `reports/investment_decision/step5b_efficient_frontier.md`
- `reports/investment_decision/time_based_figures.md`
- `reports/investment_decision/figures_index.md`

Figures:

- `reports/figures/step1_top_candidate_revenue.png`
- `reports/figures/step1_best_segment_by_city.png`
- `reports/figures/step2_knn_validation_comparison.png`
- `reports/figures/step3_revenue_scenarios.png`
- `reports/figures/step3_bootstrap_median_uncertainty.png`
- `reports/figures/step3_top_candidate_sensitivity.png`
- `reports/figures/step4_risk_score_by_candidate.png`
- `reports/figures/step4_risk_components_heatmap.png`
- `reports/figures/step4_monthly_occupancy_by_city.png`
- `reports/figures/step4_monthly_occupancy_index_by_city.png`
- `reports/figures/step5_portfolio_revenue_vs_risk.png`
- `reports/figures/step5_recommended_portfolios.png`
- `reports/figures/step5_city_occupancy_correlation.png`
- `reports/figures/step5b_efficient_frontier.png`
