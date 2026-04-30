# Step 5: Two-Property Portfolio Diversification

## Purpose

Step 5 answers whether the client should allocate a two-property investment across markets or property types. The goal is not only to maximize revenue, but also to reduce concentration, seasonality, and systematic market risk.

## Assumptions and Constraints

- Each portfolio contains two budget-feasible candidate segments from Step 1.
- This is still operating-revenue analysis, not ROI, because acquisition prices and expenses are unavailable.
- City monthly occupancy correlations are used as a diversification proxy.
- Regulatory risk remains a proxy and requires external legal due diligence.

## Method

- Built a candidate pool from the strongest decision-ready segments in each city.
- Generated all two-property combinations from that pool.
- Computed combined conservative, moderate, and optimistic revenue.
- Penalized same-city, same-neighborhood, same-property-type, high-correlation, and high-risk pairs.
- Reported three options: max revenue, diversified, and lower risk.

## Files Created

- `data/processed/investment_decision/step5_portfolio_candidate_pool.csv`
- `data/processed/investment_decision/step5_city_occupancy_correlation.csv`
- `results/investment_decision/step5_two_property_portfolio_candidates.csv`
- `results/investment_decision/step5_recommended_portfolios.csv`

## Recommended Portfolio Options

- Max revenue: Los Angeles / Hollywood Hills West / Entire home / 2BR + Los Angeles / Hollywood Hills / Entire home / 2BR. Moderate combined revenue $93,220; conservative $41,712; optimistic $148,212; risk score 0.84; city occupancy correlation 1.00.
- Diversified: Los Angeles / Hollywood Hills West / Entire home / 2BR + New York / Midtown / Entire rental unit / 0BR. Moderate combined revenue $92,736; conservative $39,688; optimistic $156,604; risk score 0.24; city occupancy correlation 0.29.
- Lower risk: New York / Fort Hamilton / Entire rental unit / 0BR + Los Angeles / Culver City / Entire home / 2BR. Moderate combined revenue $78,795; conservative $60,529; optimistic $90,075; risk score 0.00; city occupancy correlation 0.29.

## Business Interpretation

The max-revenue option may concentrate exposure in one market or property type. The diversified option is usually more appropriate for a risk-aware client because it balances revenue with lower correlation across city demand cycles. A frontier-style extension is possible from these portfolio candidates by plotting combined revenue against portfolio risk and identifying efficient pairs.
