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

- Los Angeles / Avalon / Entire condo / 2BR: conservative $43,914, moderate $123,823, optimistic $180,076. Bootstrap 90% interval for median revenue: $71,380-$143,850. k-NN median validation revenue: $142,767.
- Los Angeles / Avalon / Entire home / 2BR: conservative $33,418, moderate $85,925, optimistic $121,769. Bootstrap 90% interval for median revenue: $76,471-$111,690. k-NN median validation revenue: $112,128.
- Hawaii / North Kona / Entire serviced apartment / 1BR: conservative $22,596, moderate $66,063, optimistic $84,240. Bootstrap 90% interval for median revenue: $60,716-$84,240. k-NN median validation revenue: $84,240.
- Los Angeles / Hollywood Hills / Entire home / 2BR: conservative $17,091, moderate $61,975, optimistic $94,492. Bootstrap 90% interval for median revenue: $32,940-$82,628. k-NN median validation revenue: $83,268.
- Los Angeles / Beverly Hills / Entire rental unit / 2BR: conservative $23,422, moderate $54,486, optimistic $70,205. Bootstrap 90% interval for median revenue: $44,823-$58,718. k-NN median validation revenue: $60,756.

## Interpretation

Quartiles describe the spread of individual listing outcomes, while the bootstrap interval describes uncertainty around the typical segment revenue estimate. The strongest candidates are those with high moderate revenue, acceptable downside revenue, a reasonably narrow bootstrap interval, and k-NN validation that agrees with or exceeds the segment estimate.
