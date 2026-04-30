# Step 4: Risk Decomposition

## Purpose

Step 4 evaluates the top investment candidates by downside revenue risk, bootstrap uncertainty, seasonality, competition, and regulatory proxy risk. It also preserves full city and neighborhood systematic-risk tables.

## Risk Components

- Downside revenue risk: how far conservative revenue falls below moderate revenue.
- Bootstrap uncertainty risk: width of the bootstrap median-revenue interval relative to median revenue.
- Seasonality risk: city-level peak-to-trough monthly occupancy gap from calendar data.
- Competitive risk: budget-feasible listing count in the candidate neighborhood.
- Regulatory proxy risk: city-level qualitative score based on known need for short-term-rental due diligence.

## Files Created

- `data/processed/investment_decision/step4_city_systematic_risk.csv`
- `data/processed/investment_decision/step4_neighborhood_systematic_risk.csv`
- `results/investment_decision/step4_candidate_risk_decomposition.csv`
- `results/investment_decision/step4_risk_adjusted_rankings.csv`

## Candidate Risk Results

- Los Angeles / Avalon / Entire condo / 2BR: moderate revenue $123,823, overall risk score 0.59, risk-adjusted revenue score $77,727. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.
- Los Angeles / Avalon / Entire home / 2BR: moderate revenue $85,925, overall risk score 0.46, risk-adjusted revenue score $58,964. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.
- Hawaii / North Kona / Entire serviced apartment / 1BR: moderate revenue $66,063, overall risk score 0.44, risk-adjusted revenue score $45,759. Main regulatory note: Elevated proxy: Hawaii rules vary strongly by island/county and resort zoning.
- Los Angeles / Beverly Hills / Entire rental unit / 2BR: moderate revenue $54,486, overall risk score 0.37, risk-adjusted revenue score $39,754. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.
- Los Angeles / Hollywood Hills / Entire home / 2BR: moderate revenue $61,975, overall risk score 0.84, risk-adjusted revenue score $33,732. Main regulatory note: Elevated proxy: Los Angeles has meaningful short-term-rental compliance risk.

## Interpretation

This step does not eliminate high-revenue candidates automatically. Instead, it clarifies the tradeoff: a candidate can have superior revenue but also higher uncertainty, seasonality, competition, or regulatory exposure. The final recommendation should consider both moderate revenue and risk-adjusted ranking.
