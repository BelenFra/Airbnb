# Final Investment Decision Section

## Executive Recommendation

The strongest single-property recommendation is:

**Los Angeles / Avalon / Entire condo / 2 bedrooms**

This option is the top budget-feasible candidate after applying the $500,000 affordability rules, calendar-based operating performance, k-nearest-neighbor validation, scenario analysis, bootstrap uncertainty, and risk decomposition.

The best risk-aware two-property portfolio is:

**Los Angeles / Avalon / Entire condo / 2 bedrooms + Hawaii / North Kona / Entire serviced apartment / 1 bedroom**

This portfolio gives up some revenue versus the maximum-revenue concentrated portfolio, but it substantially improves diversification because Los Angeles and Hawaii show a negative monthly occupancy correlation in the calendar data.

## Core Investment Questions Answered

### 1. Given a $500,000 budget, what is the optimal property configuration and where?

The recommended single-property configuration is a **2-bedroom entire condo in Avalon, Los Angeles**.

Key operating metrics:

- Comparable listings in segment: `47`
- Median nightly price: `$624`
- Median calendar occupancy: `47.9%`
- Median annual revenue: `$123,823`
- Median review score: `4.67`
- Budget feasibility rule: Los Angeles can plausibly reach 1-2 bedroom condo/apartment-style units near the $500,000 budget range.

This recommendation is based on calendar-derived performance rather than only listing-level summary fields. Calendar occupancy is used as the operating source of truth, and annual revenue is computed as:

`nightly price x calendar occupancy rate x 365`

### 2. What is the projected annual revenue under different scenarios?

For the recommended Avalon 2BR condo segment:

- Conservative scenario: `$43,914`
- Moderate scenario: `$123,823`
- Optimistic scenario: `$180,076`
- Bootstrap 90% confidence interval for median revenue: `$71,380-$143,850`
- k-NN comparable median revenue: `$142,767`

The conservative, moderate, and optimistic cases come from the 25th percentile, median, and 75th percentile of the full candidate segment. Bootstrap resampling estimates uncertainty around the segment median. k-NN validation is used as a realism check using the closest comparable listings.

### 3. What are the biggest risks to this investment?

For Avalon 2BR condos, the main risks are:

- **Downside revenue risk:** conservative revenue is much lower than median revenue, indicating meaningful dispersion among listings.
- **Bootstrap uncertainty:** the 90% bootstrap interval is wide, showing uncertainty around the typical revenue estimate.
- **Seasonality risk:** Los Angeles has a `30.1%` peak-to-trough monthly occupancy gap.
- **Regulatory risk:** Los Angeles has meaningful short-term-rental compliance risk and requires external legal due diligence.
- **Competition risk:** Avalon has `128` budget-feasible comparable listings in the neighborhood universe used for risk scoring.

Despite these risks, Avalon 2BR condos still rank first on risk-adjusted revenue among the evaluated top candidates:

- Moderate revenue: `$123,823`
- Overall risk score: `0.59`
- Risk-adjusted revenue score: `$77,727`

### 4. If the client could buy two properties instead of one, how should they diversify?

The highest-revenue two-property portfolio is:

**Avalon 2BR condo + Avalon 2BR home**

- Moderate combined annual revenue: `$209,748`
- Conservative combined annual revenue: `$77,332`
- Optimistic combined annual revenue: `$301,846`
- Portfolio risk score: `0.83`
- City occupancy correlation: `1.00`

This is the maximum-revenue option, but it is highly concentrated in the same city and neighborhood.

The recommended risk-aware diversified portfolio is:

**Los Angeles / Avalon / Entire condo / 2BR + Hawaii / North Kona / Entire serviced apartment / 1BR**

- Moderate combined annual revenue: `$189,886`
- Conservative combined annual revenue: `$66,509`
- Optimistic combined annual revenue: `$264,316`
- Portfolio risk score: `0.18`
- City occupancy correlation: `-0.41`

This diversified portfolio gives up about `$19,862` in moderate revenue versus the concentrated max-revenue portfolio, but it reduces the portfolio risk score from `0.83` to `0.18`. This is the better recommendation for a risk-aware investor.

## Data Sources Used

### Internal Project Data

- `data/processed/listing_all_cleaned.csv`
- Per-city cleaned calendars (optional row-level): `data/processed/calendar/<city_slug>/calendar_<city_slug>_cleaned.csv`
- Merged row-level calendar (optional; ~3 GB): `data/processed/calendar_all_cleaned.csv`
- Listing-level occupation merge (**joined with listings for modeling**): `data/processed/occupation_all_cleaned.csv`
- `data/processed/investment_decision/step1_calendar_listing_metrics.csv`
- `data/processed/investment_decision/step1_calendar_city_month_metrics.csv`
- `data/processed/investment_decision/step1_budget_feasible_listing_metrics.csv`
- `data/processed/investment_decision/step1_decision_ready_candidate_segments.csv`
- `data/processed/investment_decision/step2_knn_comparable_listings.csv`
- `data/processed/investment_decision/step4_city_systematic_risk.csv`
- `data/processed/investment_decision/step4_neighborhood_systematic_risk.csv`
- `data/processed/investment_decision/step5_city_occupancy_correlation.csv`

### External Budget Feasibility Research

The Airbnb dataset does not contain property acquisition prices. Therefore, the $500,000 budget is used as a feasibility screen rather than as a direct ROI calculation.

Housing-market feasibility assumptions were based on the project research supplied for 2025-2026 housing conditions, including:

- Redfin $500K buying-power comparison
- Bankrate median home price data
- Market-specific interpretation of what $500K can plausibly buy by city

## Key Assumptions

### Acquisition Budget Assumption

Because purchase price is not available in the Airbnb dataset, we cannot compute true ROI, cap rate, or net yield. Instead, the analysis assumes that the client can consider only property configurations that are plausible under a $500,000 budget.

Budget-feasible rules:

- Hawaii: studio to 1BR condo/apartment-style units.
- New York: studio to 1BR in Manhattan; up to 2BR in outer boroughs.
- San Francisco: studio to small 1BR.
- Los Angeles: 1BR to 2BR condo/apartment-style units.
- Nashville: 2BR to 4BR homes, townhouses, condos, or rental units.

### Revenue Assumption

Revenue is calculated as:

`annual revenue = nightly price x calendar occupancy rate x 365`

Calendar data is used as the source of occupancy because it captures day-level availability and booked/unavailable patterns. Calendar price is used when available; when calendar price is missing, listing price is used as the nightly-rate fallback.

### Candidate Segment Assumption

The analysis evaluates segments rather than individual properties. A segment is defined as:

`city + neighborhood + property type + bedroom count`

This keeps the recommendation robust and avoids overfitting to one unusual listing.

### Decision-Ready Segment Requirements

To be decision-ready, a segment must have:

- at least `25` comparable listings
- median review score of at least `4.5`
- entire home/apartment room type
- plausible property type
- nightly price between `$50` and `$1,500`
- computed annual revenue between `$1,000` and `$250,000`

## Constraints and Limitations

### No Acquisition Price

The biggest limitation is that the Airbnb data does not include actual property acquisition prices. Therefore, the analysis cannot directly answer:

- net profit
- ROI
- cap rate
- financing-adjusted return
- cash-on-cash return

The recommendation is based on operating revenue potential among budget-plausible property types.

### No Expense Data

The analysis does not include:

- cleaning costs
- platform fees
- property taxes
- insurance
- maintenance
- HOA fees
- utilities
- property management fees
- mortgage financing

These must be layered into a final investor pro forma before a real acquisition decision.

### Regulatory Risk Is A Proxy

Regulatory risk is not directly measured in the Airbnb dataset. The analysis uses a city-level proxy score based on known need for short-term rental due diligence. This is not legal advice and should be validated externally.

### Calendar Availability Is Interpreted As Occupancy

The calendar files identify availability status. The analysis treats unavailable days as booked or occupied proxy days. This is standard for Airbnb-style analysis but can overstate true occupancy if unavailable days include owner blocks or maintenance blocks.

## Step-By-Step Analytical Process

## Step 1: Budget-Feasible Candidate Segment Universe

### Technical Method

Step 1 created a candidate universe using:

- cleaned listing attributes
- cleaned calendar occupancy
- $500K feasibility rules
- segment-level aggregation

The output segment table was grouped by:

`city + neighborhood + property type + bedrooms`

For each segment, the script calculated:

- comparable listing count
- median nightly price
- 25th and 75th percentile nightly price
- median calendar occupancy
- 25th and 75th percentile occupancy
- median annual revenue
- 25th and 75th percentile annual revenue
- median review score
- reviews per month
- revenue IQR
- risk-adjusted revenue proxy

### Key Finding

The top Step 1 segment was:

**Los Angeles / Avalon / Entire condo / 2BR**

- Median annual revenue: `$123,823`
- Median occupancy: `47.9%`
- Median nightly price: `$624`
- Comparable listings: `47`
- Median review score: `4.67`

### Business Interpretation

Avalon 2BR condos stand out because they combine high nightly price with enough calendar occupancy to generate strong annual revenue. The segment is not just a luxury-price play: it also has enough comparable listings to support the result.

### Step 1 Outputs

- `data/processed/investment_decision/step1_calendar_listing_metrics.csv`
- `data/processed/investment_decision/step1_calendar_city_month_metrics.csv`
- `data/processed/investment_decision/step1_budget_feasible_listing_metrics.csv`
- `data/processed/investment_decision/step1_all_budget_feasible_candidate_segments.csv`
- `data/processed/investment_decision/step1_decision_ready_candidate_segments.csv`
- `results/investment_decision/step1_top_candidate_segments.csv`
- `results/investment_decision/step1_city_candidate_summary.csv`
- `reports/investment_decision/step1_budget_feasible_candidates.md`

### Step 1 Figures

- `reports/figures/05_investment_decision/step1_top_candidate_revenue.png`
- `reports/figures/05_investment_decision/step1_best_segment_by_city.png`

## Step 2: k-NN Comparable Listing Validation

### Technical Method

Step 2 validated the top five Step 1 candidates with k-nearest-neighbor comparable listings.

The k-NN distance used:

- bedroom count
- bathrooms
- beds
- nightly price
- occupancy rate
- review score
- reviews per month

The comparable pool prioritized:

1. same city
2. same neighborhood
3. same property type
4. same bedroom count

Each candidate was validated against the `15` nearest comparable listings.

### Key Finding

For the recommended Avalon 2BR condo:

- Step 1 segment median revenue: `$123,823`
- k-NN median revenue: `$142,767`
- k-NN p25 revenue: `$126,664`
- k-NN p75 revenue: `$191,912`
- k-NN median occupancy: `69.3%`
- k-NN median nightly price: `$684`
- validation status: supported by close comps

### Business Interpretation

The k-NN results strengthen the recommendation. The closest real comparable listings perform above the segment median, which suggests the segment result is not being driven only by broad averages.

### Step 2 Outputs

- `data/processed/investment_decision/step2_knn_comparable_listings.csv`
- `results/investment_decision/step2_knn_candidate_validation_summary.csv`
- `reports/investment_decision/step2_knn_comparable_validation.md`

### Step 2 Figure

- `reports/figures/05_investment_decision/step2_knn_validation_comparison.png`

## Step 3: Revenue Scenarios and Bootstrap Uncertainty

### Technical Method

Step 3 used full segment distributions as the primary scenario basis.

Scenarios:

- Conservative: 25th percentile of segment revenue
- Moderate: median segment revenue
- Optimistic: 75th percentile of segment revenue

Bootstrap:

- `1,000` bootstrap resamples
- statistic: median annual revenue
- interval: 90% bootstrap confidence interval

Sensitivity tests:

- base median case
- price down 10%
- occupancy down 10 percentage points
- both price and occupancy downside
- price up 10% and occupancy up 5 percentage points

### Key Finding

For Avalon 2BR condos:

- Conservative revenue: `$43,914`
- Moderate revenue: `$123,823`
- Optimistic revenue: `$180,076`
- Bootstrap 90% interval for median revenue: `$71,380-$143,850`
- k-NN validation median revenue: `$142,767`

### Business Interpretation

The Avalon 2BR condo opportunity has high upside, but also meaningful revenue dispersion. The conservative scenario is much lower than the median, meaning execution, exact unit quality, guest experience, and listing positioning matter.

The bootstrap interval supports the conclusion that typical revenue is attractive, but it also warns that the median estimate is uncertain because the segment has only `47` comparable listings.

### Step 3 Outputs

- `results/investment_decision/step3_revenue_scenarios.csv`
- `results/investment_decision/step3_bootstrap_revenue_uncertainty.csv`
- `results/investment_decision/step3_sensitivity_analysis.csv`
- `reports/investment_decision/step3_bootstrap_scenarios.md`

### Step 3 Figures

- `reports/figures/05_investment_decision/step3_revenue_scenarios.png`
- `reports/figures/05_investment_decision/step3_bootstrap_median_uncertainty.png`
- `reports/figures/05_investment_decision/step3_top_candidate_sensitivity.png`

## Step 4: Risk Decomposition

### Technical Method

Step 4 decomposed risk into:

- downside revenue risk
- bootstrap uncertainty risk
- seasonality risk
- competition risk
- regulatory proxy risk

It also preserved full systematic-risk tables for city and neighborhood analysis.

Seasonality was measured from monthly calendar occupancy:

- average monthly occupancy
- minimum monthly occupancy
- maximum monthly occupancy
- standard deviation
- peak-to-trough gap
- coefficient of variation

### Candidate Risk Ranking

Top candidate risk-adjusted results:

1. Avalon 2BR condo:
   - moderate revenue: `$123,823`
   - overall risk score: `0.59`
   - risk-adjusted revenue score: `$77,727`

2. Avalon 2BR home:
   - moderate revenue: `$85,925`
   - overall risk score: `0.46`
   - risk-adjusted revenue score: `$58,964`

3. North Kona 1BR serviced apartment:
   - moderate revenue: `$66,063`
   - overall risk score: `0.44`
   - risk-adjusted revenue score: `$45,759`

4. Beverly Hills 2BR rental unit:
   - moderate revenue: `$54,486`
   - overall risk score: `0.37`
   - risk-adjusted revenue score: `$39,754`

5. Hollywood Hills 2BR home:
   - moderate revenue: `$61,975`
   - overall risk score: `0.84`
   - risk-adjusted revenue score: `$33,732`

### Systematic Market Risk

City-level seasonality and systematic risk:

- Nashville: average occupancy `33.0%`, peak-to-trough gap `37.0%`, coefficient of variation `0.35`
- Los Angeles: average occupancy `43.2%`, peak-to-trough gap `30.1%`, coefficient of variation `0.22`
- Hawaii: average occupancy `37.6%`, peak-to-trough gap `28.4%`, coefficient of variation `0.23`
- San Francisco: average occupancy `47.9%`, peak-to-trough gap `28.4%`, coefficient of variation `0.18`
- New York: average occupancy `56.3%`, peak-to-trough gap `22.6%`, coefficient of variation `0.12`

### Business Interpretation

Avalon 2BR condos remain the top risk-adjusted single-property candidate despite elevated Los Angeles regulatory proxy risk and revenue uncertainty. Hollywood Hills has meaningful revenue potential but ranks worse after risk adjustment because of high downside and uncertainty.

### Step 4 Outputs

- `data/processed/investment_decision/step4_city_systematic_risk.csv`
- `data/processed/investment_decision/step4_neighborhood_systematic_risk.csv`
- `results/investment_decision/step4_candidate_risk_decomposition.csv`
- `results/investment_decision/step4_risk_adjusted_rankings.csv`
- `reports/investment_decision/step4_risk_decomposition.md`
- `reports/investment_decision/time_based_figures.md`

### Step 4 Figures

- `reports/figures/05_investment_decision/step4_risk_score_by_candidate.png`
- `reports/figures/05_investment_decision/step4_risk_components_heatmap.png`
- `reports/figures/05_investment_decision/step4_city_seasonality.png`
- `reports/figures/05_investment_decision/step4_monthly_occupancy_by_city.png`
- `reports/figures/05_investment_decision/step4_monthly_occupancy_index_by_city.png`

## Step 5: Two-Property Portfolio Diversification

### Technical Method

Step 5 generated two-property portfolio combinations from the broader decision-ready candidate pool.

For each portfolio, the model calculated:

- combined conservative revenue
- combined moderate revenue
- combined optimistic revenue
- downside ratio
- segment uncertainty
- city systematic risk
- regulatory risk proxy
- concentration penalty
- diversification bonus
- city occupancy correlation
- portfolio risk score
- risk-adjusted revenue score

### Portfolio Options

#### Max Revenue Portfolio

**Avalon 2BR condo + Avalon 2BR home**

- moderate combined revenue: `$209,748`
- conservative combined revenue: `$77,332`
- optimistic combined revenue: `$301,846`
- portfolio risk score: `0.83`
- city occupancy correlation: `1.00`

Business interpretation: strongest revenue but highly concentrated in the same city and neighborhood.

#### Diversified Portfolio

**Avalon 2BR condo + North Kona 1BR serviced apartment**

- moderate combined revenue: `$189,886`
- conservative combined revenue: `$66,509`
- optimistic combined revenue: `$264,316`
- portfolio risk score: `0.18`
- city occupancy correlation: `-0.41`

Business interpretation: best risk-aware two-property recommendation. It preserves most of the revenue upside while reducing concentration and seasonal correlation risk.

#### Lower-Risk Portfolio

**Echo Park 2BR home + North Shore Kauai 0BR rental unit**

- moderate combined revenue: `$83,036`
- conservative combined revenue: `$66,037`
- optimistic combined revenue: `$111,268`
- portfolio risk score: `0.00`

Business interpretation: lowest risk but much lower revenue potential.

### Step 5 Outputs

- `data/processed/investment_decision/step5_portfolio_candidate_pool.csv`
- `data/processed/investment_decision/step5_city_occupancy_correlation.csv`
- `results/investment_decision/step5_two_property_portfolio_candidates.csv`
- `results/investment_decision/step5_recommended_portfolios.csv`
- `reports/investment_decision/step5_portfolio_diversification.md`

### Step 5 Figures

- `reports/figures/05_investment_decision/step5_portfolio_revenue_vs_risk.png`
- `reports/figures/05_investment_decision/step5_recommended_portfolios.png`
- `reports/figures/05_investment_decision/step5_city_occupancy_correlation.png`

## Step 5B: Efficient Frontier

### Technical Method

Step 5B created a simple efficient frontier from the two-property portfolio table.

A portfolio is on the frontier if no other portfolio has both:

- lower or equal risk
- higher or equal revenue

This is not a finance-grade mean-variance frontier because the dataset does not contain acquisition cost, expenses, or true return variance. It is a decision-support frontier using operating revenue and composite risk.

### Key Frontier Results

Lowest-risk frontier portfolio:

**Echo Park 2BR home + North Shore Kauai 0BR rental unit**

- revenue: `$83,036`
- risk: `0.00`

Highest-revenue frontier portfolio:

**Avalon 2BR condo + Avalon 2BR home**

- revenue: `$209,748`
- risk: `0.83`

Best balanced-score frontier portfolio:

**Avalon 2BR condo + North Kona 1BR serviced apartment**

- revenue: `$189,886`
- risk: `0.18`

### Business Interpretation

The efficient frontier confirms that the diversified LA + Hawaii portfolio is the strongest risk-aware portfolio. It sacrifices about `$19,862` in moderate revenue compared with the max-revenue same-neighborhood Avalon portfolio, but it reduces risk dramatically.

### Step 5B Outputs

- `results/investment_decision/step5b_efficient_frontier_portfolios.csv`
- `reports/investment_decision/step5b_efficient_frontier.md`

### Step 5B Figure

- `reports/figures/05_investment_decision/step5b_efficient_frontier.png`

## Final Business Interpretation

The investment section points to a clear conclusion:

**For a single-property strategy, choose a Los Angeles / Avalon / 2-bedroom entire condo.**

The case for this recommendation is strong because:

- It is budget-plausible under the $500K feasibility screen.
- It has the highest calendar-based median annual revenue among decision-ready candidates.
- It is supported by 47 segment comps.
- Its k-NN closest comps show even stronger median revenue.
- It remains first after risk-adjusted revenue scoring.
- Its moderate revenue is materially higher than the next-best single-property candidates.

However, this is not a low-risk investment. The downside case is materially lower than the median, and Los Angeles carries meaningful regulatory proxy risk. Therefore, the client should treat this as a high-upside investment that requires careful unit selection, compliance review, and operational execution.

For a two-property strategy, the recommendation changes:

**Choose Avalon 2BR condo + North Kona 1BR serviced apartment.**

This portfolio is preferable for a risk-aware client because it:

- keeps high combined revenue
- diversifies across Los Angeles and Hawaii
- has negative city occupancy correlation
- appears on the efficient frontier
- reduces risk score substantially versus the max-revenue concentrated Avalon pair

## Final Recommendation

### If Buying One Property

Buy or target:

**2-bedroom entire condo in Avalon, Los Angeles**

Expected operating revenue:

- conservative: `$43,914`
- moderate: `$123,823`
- optimistic: `$180,076`

Use the k-NN comp result as an upside validation:

- closest comparable median revenue: `$142,767`

### If Buying Two Properties

Use a diversified two-market allocation:

1. **Los Angeles / Avalon / Entire condo / 2BR**
2. **Hawaii / North Kona / Entire serviced apartment / 1BR**

Expected combined operating revenue:

- conservative: `$66,509`
- moderate: `$189,886`
- optimistic: `$264,316`

This is the recommended two-property strategy because it balances revenue and diversification better than buying two properties in Avalon.

## Final Caveats Before Acquisition

Before turning this analytics recommendation into a real purchase decision, the client should verify:

- actual property acquisition price
- HOA and condo restrictions
- short-term rental legality and permitting
- taxes and insurance
- cleaning and management costs
- expected maintenance
- financing terms
- local demand shocks
- whether unavailable calendar days reflect bookings or owner blocks

The analysis supports where to look first. It does not replace legal, financing, and property-level due diligence.

