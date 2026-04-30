# Step 1: Budget-Feasible Candidate Segment Universe

## Purpose

This step defines what a $500,000 investor can plausibly buy in each market, then ranks those feasible Airbnb segments by observed operating performance. Because the Airbnb dataset does not contain purchase prices, the budget is used as a feasibility screen rather than a true ROI calculation.

## Data Used

- `data/processed/master_data.csv` is the source of truth for this step. It already merges listing attributes with calendar-derived operating fields.
- `estimated_revenue_l365d` is used as observed annual revenue when available.
- `occupancy_rate_proxy` and `estimated_occupancy_l365d` provide listing-level occupancy information.
- Nightly price is inferred as `estimated revenue / estimated occupied nights` when possible; otherwise, listing `price` is used as the fallback.

## Housing Feasibility Rules Used

- Hawaii: studio to 1BR condo/apartment-style units.
- New York: studio to 1BR in Manhattan; up to 2BR in outer boroughs.
- San Francisco: studio to small 1BR.
- Los Angeles: 1BR to 2BR condo/apartment-style units.
- Nashville: 2BR to 4BR homes, townhouses, condos, or rental units.

These rules are based on the current housing-market research supplied for the project, including Redfin's 2025 $500K buying-power comparison and Bankrate's 2025 state median home price data.

## Airbnb Filters

- Entire home/apartment listings only.
- Plausible property types: condo, rental unit, home, townhouse, guest suite, serviced apartment, loft, bungalow, cottage, or apartment.
- Nightly price between $50 and $1,500.
- Calendar-derived occupancy proxy between 0% and 100%.
- Computed annual revenue between $1,000 and $250,000.
- Decision-ready segments require at least 25 comparable listings and median review score of at least 4.5.

## Files Created

- `data/processed/investment_decision/step1_calendar_listing_metrics.csv`
- `data/processed/investment_decision/step1_budget_feasible_listing_metrics.csv`
- `data/processed/investment_decision/step1_all_budget_feasible_candidate_segments.csv`
- `data/processed/investment_decision/step1_decision_ready_candidate_segments.csv`
- `results/investment_decision/step1_top_candidate_segments.csv`
- `results/investment_decision/step1_city_candidate_summary.csv`

## Results

Budget-feasible listing records analyzed: 38,712

All budget-feasible segments created: 3,351

Decision-ready segments after sample/review filters: 243

Top decision-ready candidate segments:

- Los Angeles / Hollywood Hills West / Entire home / 2BR: median annual revenue $47,628, median occupancy 38.1%, median nightly price $376, 46 comparable listings, median review score 4.95.
- Los Angeles / Hollywood Hills / Entire home / 2BR: median annual revenue $45,592, median occupancy 50.4%, median nightly price $356, 52 comparable listings, median review score 4.94.
- Los Angeles / Silver Lake / Entire home / 2BR: median annual revenue $45,138, median occupancy 51.0%, median nightly price $250, 54 comparable listings, median review score 4.95.
- New York / Midtown / Entire rental unit / 0BR: median annual revenue $45,108, median occupancy 49.6%, median nightly price $252, 151 comparable listings, median review score 4.61.
- Los Angeles / Manhattan Beach / Entire home / 2BR: median annual revenue $43,968, median occupancy 34.2%, median nightly price $390, 26 comparable listings, median review score 4.87.
- Nashville / District 19 / Entire home / 4BR: median annual revenue $42,000, median occupancy 13.7%, median nightly price $373, 107 comparable listings, median review score 4.94.
- New York / Fort Hamilton / Entire rental unit / 0BR: median annual revenue $41,055, median occupancy 10.1%, median nightly price $161, 50 comparable listings, median review score 4.67.
- Nashville / District 19 / Entire condo / 3BR: median annual revenue $40,382, median occupancy 10.1%, median nightly price $321, 30 comparable listings, median review score 4.92.
- Los Angeles / Santa Monica / Entire home / 2BR: median annual revenue $39,960, median occupancy 33.2%, median nightly price $302, 27 comparable listings, median review score 4.92.
- Los Angeles / Highland Park / Entire home / 2BR: median annual revenue $39,420, median occupancy 52.9%, median nightly price $221, 37 comparable listings, median review score 4.95.

## Interpretation

This step does not choose the final investment yet. It creates the defensible candidate universe using the merged master dataset's calendar-derived operating performance. The next step should use k-nearest-neighbor comparable listings to validate whether the highest-ranked segments are supported by similar individual properties, not just by segment medians.
