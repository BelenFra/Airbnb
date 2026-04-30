# Step 2: k-NN Comparable Listing Validation

## Purpose

Step 1 ranked budget-feasible candidate segments. Step 2 checks whether those segment-level recommendations are supported by similar individual listings. This is important because a segment median can look attractive even when the closest actual listings perform differently.

## Method

- Took the top 5 Step 1 candidate segments.
- Built a comparable-listing pool for each candidate, prioritizing same city, neighborhood, property type, and bedroom count.
- Used a k-nearest-neighbor distance based on bedroom count, bathrooms, beds, nightly price, occupancy, review score, and reviews per month.
- Selected the 15 closest comparable listings for each candidate.
- Compared k-NN median revenue with the Step 1 segment median revenue.

## Files Created

- `data/processed/investment_decision/step2_knn_comparable_listings.csv`
- `results/investment_decision/step2_knn_candidate_validation_summary.csv`

## Results

- Los Angeles / Avalon / Entire condo / 2BR: Step 1 median revenue $123,823; k-NN median revenue $142,767; k-NN revenue range $126,664-$191,912; status: supported by close comps.
- Los Angeles / Avalon / Entire home / 2BR: Step 1 median revenue $85,925; k-NN median revenue $112,128; k-NN revenue range $82,064-$128,687; status: supported by close comps.
- Hawaii / North Kona / Entire serviced apartment / 1BR: Step 1 median revenue $66,063; k-NN median revenue $84,240; k-NN revenue range $66,063-$84,240; status: supported by close comps.
- Los Angeles / Hollywood Hills / Entire home / 2BR: Step 1 median revenue $61,975; k-NN median revenue $83,268; k-NN revenue range $37,210-$100,140; status: supported by close comps.
- Los Angeles / Beverly Hills / Entire rental unit / 2BR: Step 1 median revenue $54,486; k-NN median revenue $60,756; k-NN revenue range $55,144-$70,030; status: supported by close comps.

## Interpretation

Candidates whose k-NN median revenue is close to the segment median are more credible because similar real listings support the segment result. Candidates with weaker k-NN performance should be treated cautiously or moved behind better-supported alternatives.
