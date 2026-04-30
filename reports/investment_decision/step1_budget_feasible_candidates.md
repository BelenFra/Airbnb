# Step 1: Budget-Feasible Candidate Segment Universe

## Purpose

This step defines what a $500,000 investor can plausibly buy in each market, then ranks those feasible Airbnb segments by observed operating performance. Because the Airbnb dataset does not contain purchase prices, the budget is used as a feasibility screen rather than a true ROI calculation.

## Data Used

- Calendar files are the operating-performance source of truth for occupancy. They provide listing-level booked days, available days, and calendar days.
- Calendar price is used when available. If calendar price is missing, the cleaned listing price is used as the nightly-price fallback.
- Cleaned listings provide city, neighborhood, property type, bedroom count, review score, and listing attributes.
- Annual revenue is computed as `nightly price x calendar occupancy rate x 365`.

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
- Calendar occupancy rate between 0% and 100%.
- Computed annual revenue between $1,000 and $250,000.
- Decision-ready segments require at least 25 comparable listings and median review score of at least 4.5.

## Files Created

- `data/processed/investment_decision/step1_calendar_listing_metrics.csv`
- `data/processed/investment_decision/step1_calendar_city_month_metrics.csv`
- `data/processed/investment_decision/step1_budget_feasible_listing_metrics.csv`
- `data/processed/investment_decision/step1_all_budget_feasible_candidate_segments.csv`
- `data/processed/investment_decision/step1_decision_ready_candidate_segments.csv`
- `results/investment_decision/step1_top_candidate_segments.csv`
- `results/investment_decision/step1_city_candidate_summary.csv`

## Results

Budget-feasible listing records analyzed: 34,149

All budget-feasible segments created: 3,182

Decision-ready segments after sample/review filters: 209

Top decision-ready candidate segments:

- Los Angeles / Avalon / Entire condo / 2BR: median annual revenue $123,823, median occupancy 47.9%, median nightly price $624, 47 comparable listings, median review score 4.67.
- Los Angeles / Avalon / Entire home / 2BR: median annual revenue $85,925, median occupancy 49.6%, median nightly price $463, 33 comparable listings, median review score 4.61.
- Hawaii / North Kona / Entire serviced apartment / 1BR: median annual revenue $66,063, median occupancy 96.2%, median nightly price $240, 27 comparable listings, median review score 4.72.
- Los Angeles / Hollywood Hills / Entire home / 2BR: median annual revenue $61,975, median occupancy 50.1%, median nightly price $360, 43 comparable listings, median review score 4.95.
- Los Angeles / Beverly Hills / Entire rental unit / 2BR: median annual revenue $54,486, median occupancy 63.0%, median nightly price $225, 108 comparable listings, median review score 4.67.
- Los Angeles / Hollywood Hills West / Entire home / 2BR: median annual revenue $50,700, median occupancy 39.5%, median nightly price $383, 37 comparable listings, median review score 4.94.
- Hawaii / Lahaina / Entire home / 1BR: median annual revenue $47,285, median occupancy 42.7%, median nightly price $257, 27 comparable listings, median review score 4.85.
- Los Angeles / Echo Park / Entire home / 2BR: median annual revenue $46,580, median occupancy 60.4%, median nightly price $223, 32 comparable listings, median review score 4.92.
- Hawaii / North Shore Kauai / Entire rental unit / 1BR: median annual revenue $44,982, median occupancy 78.4%, median nightly price $185, 159 comparable listings, median review score 4.91.
- Hawaii / Koloa-Poipu / Entire condo / 0BR: median annual revenue $44,628, median occupancy 50.5%, median nightly price $242, 28 comparable listings, median review score 4.86.

## Interpretation

This step does not choose the final investment yet. It creates the defensible candidate universe using calendar-based operating performance. The next step should use k-nearest-neighbor comparable listings to validate whether the highest-ranked segments are supported by similar individual properties, not just by segment medians.
