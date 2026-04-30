# Step 3: Revenue Scenarios and Bootstrap Uncertainty

## Purpose

Step 3 estimates conservative, moderate, and optimistic annual revenue for the validated candidate segments. It also uses bootstrap resampling to quantify uncertainty around the segment median revenue.

## Method

- Primary scenarios use the full Step 1 candidate segment, not only the 15 k-NN neighbors.
- Conservative scenario = 25th percentile of segment comps.
- Moderate scenario = median of segment comps.
- Optimistic scenario = 75th percentile of segment comps.
- Bootstrap uncertainty uses 1,000 resamples of segment annual revenue and reports a 90% interval for the median.
- k-NN median revenue from Step 2 is included as validation, not as the primary scenario basis.
- Sensitivity tests stress price and occupancy separately and together.

## Files Created

- `results/investment_decision/step3_revenue_scenarios.csv`
- `results/investment_decision/step3_bootstrap_revenue_uncertainty.csv`
- `results/investment_decision/step3_sensitivity_analysis.csv`

## Results

- Los Angeles / Hollywood Hills West / Entire home / 2BR: conservative $20,100, moderate $47,628, optimistic $78,957. Bootstrap 90% interval for median revenue: $37,638-$63,627. k-NN median validation revenue: $47,640.
- Los Angeles / Hollywood Hills / Entire home / 2BR: conservative $21,612, moderate $45,592, optimistic $69,255. Bootstrap 90% interval for median revenue: $35,820-$50,946. k-NN median validation revenue: $37,980.
- Los Angeles / Silver Lake / Entire home / 2BR: conservative $21,948, moderate $45,138, optimistic $59,181. Bootstrap 90% interval for median revenue: $33,759-$50,164. k-NN median validation revenue: $32,706.
- New York / Midtown / Entire rental unit / 0BR: conservative $19,588, moderate $45,108, optimistic $77,648. Bootstrap 90% interval for median revenue: $36,210-$60,288. k-NN median validation revenue: $34,565.
- Los Angeles / Manhattan Beach / Entire home / 2BR: conservative $18,207, moderate $43,968, optimistic $64,850. Bootstrap 90% interval for median revenue: $20,628-$54,062. k-NN median validation revenue: $21,060.

## Interpretation

Quartiles describe the spread of individual listing outcomes, while the bootstrap interval describes uncertainty around the typical segment revenue estimate. The strongest candidates are those with high moderate revenue, acceptable downside revenue, a reasonably narrow bootstrap interval, and k-NN validation that agrees with or exceeds the segment estimate.
