# Q2 — Price · Occupancy · Revenue across cities

**Question.** How do average nightly prices, occupancy rates and estimated annual revenues compare across the five cities?

## Method

- One row per cleaned listing in `master_data.csv`.
- `est_annual_revenue = price × 365 × occupancy_rate_proxy` (consistent across cities).
- We report mean and median for price, occupancy and revenue per city plus a rank.

## Headline

- Most expensive (median nightly): **Hawaii** ($233)
- Highest mean occupancy: **San Francisco** (39%)
- Largest median annual revenue: **Hawaii** ($26,582)

## Per-city summary

| City          |   listings | mean_price   | median_price   | p25_price   | p75_price   | mean_occupancy   | median_occupancy   | mean_revenue   | median_revenue   |   mean_price_rank |   mean_occupancy_rank |   mean_revenue_rank |
|:--------------|-----------:|:-------------|:---------------|:------------|:------------|:-----------------|:-------------------|:---------------|:-----------------|------------------:|----------------------:|--------------------:|
| Hawaii        |      33132 | $945         | $233           | $155        | $400        | 37.0%            | 31.0%              | $185,990       | $26,582          |                 1 |                     2 |                   1 |
| Los Angeles   |      36819 | $342         | $155           | $95         | $260        | 30.0%            | 25.0%              | $30,749        | $10,300          |                 4 |                     4 |                   4 |
| Nashville     |       6634 | $223         | $158           | $109        | $236        | 28.0%            | 16.0%              | $21,022        | $10,808          |                 5 |                     5 |                   5 |
| New York      |      21328 | $681         | $154           | $89         | $279        | 31.0%            | 24.0%              | $62,300        | $12,167          |                 2 |                     3 |                   2 |
| San Francisco |       5795 | $379         | $170           | $105        | $285        | 39.0%            | 33.0%              | $41,007        | $18,256          |                 3 |                     1 |                   3 |

## Files

- Per-city summary CSV: `results/01_market_analysis/q2_price_occupancy_revenue/per_city_summary.csv`
- Figure: `reports/figures/market_analysis/q2_price_occupancy_revenue/01_q2_price_distribution.png`
- Figure: `reports/figures/market_analysis/q2_price_occupancy_revenue/02_q2_occupancy_distribution.png`
- Figure: `reports/figures/market_analysis/q2_price_occupancy_revenue/03_q2_three_metric_comparison.png`
