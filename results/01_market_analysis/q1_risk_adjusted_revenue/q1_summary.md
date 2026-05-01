# Q1 — Risk-adjusted revenue per city

**Question.** Which city offers the best risk-adjusted revenue opportunity for a new Airbnb investment?

## Method

- Per-listing annual revenue proxy: `price × 365 × occupancy_rate_proxy`.
- We use the same formula in every city to keep methodology consistent. 
  (We do not use Inside Airbnb's `estimated_revenue_l365d` because in NYC it is mostly
  zero due to Local Law 18 caps and would penalise NYC unfairly.)
- *Risk-adjusted* metrics:
  - **Sharpe-style (mean / std)** — classic, sensitive to outliers.
  - **median / IQR** — robust alternative, recommended for the long-tailed revenue distribution.

## Headline numbers

| City          |   listings | median_price   | median_occupancy   | mean_revenue   | median_revenue   | std_revenue   | p10_revenue   | p25_revenue   | p75_revenue   | p90_revenue   | iqr_revenue   |   sharpe_mean_std |   sharpe_median_iqr |   sharpe_mean_std_rank |   sharpe_median_iqr_rank |
|:--------------|-----------:|:---------------|:-------------------|:---------------|:-----------------|:--------------|:--------------|:--------------|:--------------|:--------------|:--------------|------------------:|--------------------:|-----------------------:|-------------------------:|
| Hawaii        |      33132 | $233           | 31.0%              | $185,990       | $26,582          | $1,307,954    | $2,700        | $10,615       | $57,915       | $134,603      | $47,300       |             0.142 |               0.562 |                      4 |                        1 |
| Los Angeles   |      36819 | $155           | 25.0%              | $30,749        | $10,300          | $116,568      | $0            | $1,200        | $29,952       | $63,450       | $28,752       |             0.264 |               0.358 |                      3 |                        5 |
| Nashville     |       6634 | $158           | 16.0%              | $21,022        | $10,808          | $78,170       | $1,583        | $3,841        | $25,303       | $45,402       | $21,462       |             0.269 |               0.504 |                      2 |                        2 |
| New York      |      21328 | $154           | 24.0%              | $62,300        | $12,167          | $533,409      | $0            | $2,250        | $30,801       | $65,805       | $28,551       |             0.117 |               0.426 |                      5 |                        4 |
| San Francisco |       5795 | $170           | 33.0%              | $41,007        | $18,256          | $148,459      | $732          | $5,918        | $42,385       | $80,585       | $36,466       |             0.276 |               0.501 |                      1 |                        3 |

## Business reading

- **Best risk-adjusted (median / IQR): Hawaii** — highest typical revenue per unit of cross-listing dispersion.
- **Highest typical revenue (median): Hawaii**.
- **Most homogeneous market (smallest IQR): Nashville** — risk is lowest but absolute returns may be smaller.

> **Why median, not mean?** The mean revenue is distorted by extreme listings (e.g.
> Hawaii's `price` reaches $85,000 on luxury villas). For Hawaii ``mean_revenue`` is
> ~7× the median, which is why we report median + IQR as the headline robustness
> metric and keep `sharpe_mean_std` only as a secondary cross-check.

Use the **return vs. risk** scatter (Plot 3) to weigh the trade-off; 
a city in the top-left (high median, low IQR) is the prime candidate.

## Files

- Per-city metrics CSV: `results/01_market_analysis/q1_risk_adjusted_revenue/per_city_metrics.csv`
- Figure: `reports/figures/01_market_analysis/q1_risk_adjusted_revenue/01_q1_revenue_boxplot.png`
- Figure: `reports/figures/01_market_analysis/q1_risk_adjusted_revenue/02_q1_sharpe_ranking.png`
- Figure: `reports/figures/01_market_analysis/q1_risk_adjusted_revenue/03_q1_return_vs_risk.png`
