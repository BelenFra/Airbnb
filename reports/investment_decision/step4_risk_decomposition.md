# Step 4: Risk Decomposition

## Purpose

Step 4 evaluates the top investment candidates by downside revenue risk, bootstrap uncertainty, calendar seasonality, competition, scrape-date freshness, and regulatory proxy risk.

## Data Used

- Listing and annual revenue inputs come from `data/processed/master_data.csv` through the Step 1 outputs.
- Monthly seasonality comes from `data/processed/calendars/calendar_all_cleaned.csv`.
- `calendar_last_scraped` is used as a data-freshness/snapshot-consistency check, not as a seasonality variable.

## Risk Components

- Downside revenue risk: how far conservative revenue falls below moderate revenue.
- Bootstrap uncertainty risk: width of the bootstrap median-revenue interval relative to median revenue.
- Seasonality risk: city-level peak-to-trough monthly occupancy gap from the combined calendar file.
- Competitive risk: budget-feasible listing count in the candidate neighborhood.
- Freshness risk: spread in `calendar_last_scraped` dates within a city.
- Regulatory proxy risk: city-level qualitative score based on known need for short-term-rental due diligence.

## Files Created

- `data/processed/investment_decision/step4_calendar_city_month_metrics.csv`
- `data/processed/investment_decision/step4_calendar_scrape_freshness.csv`
- `data/processed/investment_decision/step4_city_systematic_risk.csv`
- `data/processed/investment_decision/step4_neighborhood_systematic_risk.csv`
- `results/investment_decision/step4_candidate_risk_decomposition.csv`
- `results/investment_decision/step4_risk_adjusted_rankings.csv`

## Candidate Risk Results

- Los Angeles / Silver Lake / Entire home / 2BR: moderate revenue $45,138, seasonality gap 30.1%, overall risk score 0.42, risk-adjusted revenue score $31,764. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.
- Los Angeles / Hollywood Hills / Entire home / 2BR: moderate revenue $45,592, seasonality gap 30.1%, overall risk score 0.44, risk-adjusted revenue score $31,741. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.
- Los Angeles / Hollywood Hills West / Entire home / 2BR: moderate revenue $47,628, seasonality gap 30.1%, overall risk score 0.66, risk-adjusted revenue score $28,614. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.
- New York / Midtown / Entire rental unit / 0BR: moderate revenue $45,108, seasonality gap 22.6%, overall risk score 0.59, risk-adjusted revenue score $28,384. Main regulatory note: High proxy: NYC short-term-rental regulation is a major due-diligence item.
- Los Angeles / Manhattan Beach / Entire home / 2BR: moderate revenue $43,968, seasonality gap 30.1%, overall risk score 0.85, risk-adjusted revenue score $23,786. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.

## Interpretation

This step now separates the two sources cleanly: master data supports listing/segment economics, while the combined calendar file supports monthly seasonality and snapshot freshness. A candidate can have superior revenue but still carry higher uncertainty, seasonality, competition, freshness, or regulatory exposure.
