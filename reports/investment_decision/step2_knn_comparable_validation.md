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

- Los Angeles / Hollywood Hills West / Entire home / 2BR: Step 1 median revenue $47,628; k-NN median revenue $47,640; k-NN revenue range $29,319-$62,135; status: supported by close comps.
- Los Angeles / Hollywood Hills / Entire home / 2BR: Step 1 median revenue $45,592; k-NN median revenue $37,980; k-NN revenue range $26,700-$63,270; status: weaker than segment median in close comps.
- Los Angeles / Silver Lake / Entire home / 2BR: Step 1 median revenue $45,138; k-NN median revenue $32,706; k-NN revenue range $9,970-$49,600; status: weaker than segment median in close comps.
- New York / Midtown / Entire rental unit / 0BR: Step 1 median revenue $45,108; k-NN median revenue $34,565; k-NN revenue range $20,120-$51,958; status: weaker than segment median in close comps.
- Los Angeles / Manhattan Beach / Entire home / 2BR: Step 1 median revenue $43,968; k-NN median revenue $21,060; k-NN revenue range $17,066-$43,968; status: weaker than segment median in close comps.

## Interpretation

Candidates whose k-NN median revenue is close to the segment median are more credible because similar real listings support the segment result. Candidates with weaker k-NN performance should be treated cautiously or moved behind better-supported alternatives.
