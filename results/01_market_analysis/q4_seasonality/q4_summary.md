# Q4 — Seasonality of demand & revenue per city

**Question.** How does seasonality affect revenue in each city? Is demand stable year-round or concentrated in peak months?

## Method

- We stream `data/processed/calendar_all_cleaned.csv` (~3 GB) in chunks and aggregate
  per (city, year-month) — chunk size = 1,500,000 rows.
- **Partial-month filter**: months whose row count is below 85% of
  the city's largest month are dropped. The Inside Airbnb snapshot was scraped in
  Sept 2025, so the first and last month per city are partial; keeping them would
  bias the seasonality strength downward (low demand because few days were observed).
- `demand_proxy` = 1 − mean(available)
- `median_listing_price` = constant per city, taken from the cleaned `master_data.csv`.
  The Inside Airbnb calendar leaves `price`/`adjusted_price` empty (documented in the
  calendar cleaning memo), so we cannot estimate per-month price seasonality from the
  snapshot — only demand seasonality.
- `revenue_per_listing` = `demand_proxy × median_listing_price × days_in_month`
- Seasonality strength: coefficient of variation (CV = std / mean across months).

## Headline

- Most seasonal revenue: **Nashville** (revenue CV = 0.33).
- Most stable revenue: **New York** (revenue CV = 0.13).

## Per-city seasonality summary

| City          |   n_months | demand_mean   |   demand_std |   demand_cv | demand_peak_month   | demand_peak_value   | demand_low_month   | demand_low_value   |   demand_peak_to_low | revenue_mean   | revenue_std   |   revenue_cv | revenue_peak_month   | revenue_peak_value   | revenue_low_month   | revenue_low_value   |   revenue_peak_to_low |
|:--------------|-----------:|:--------------|-------------:|------------:|:--------------------|:--------------------|:-------------------|:-------------------|---------------------:|:---------------|:--------------|-------------:|:---------------------|:---------------------|:--------------------|:--------------------|----------------------:|
| Hawaii        |         11 | 36.6%         |        0.075 |      0.2049 | 2025-10             | 48.0%               | 2026-05            | 26.5%              |                 1.81 | $2,592         | $528          |       0.2036 | 2025-10              | $3,468               | 2026-05             | $1,914              |                  1.81 |
| Los Angeles   |         12 | 41.6%         |        0.081 |      0.1942 | 2026-06             | 52.8%               | 2025-11            | 31.9%              |                 1.66 | $1,964         | $396          |       0.2016 | 2026-07              | $2,532               | 2026-02             | $1,428              |                  1.77 |
| Nashville     |         11 | 30.2%         |        0.096 |      0.3172 | 2025-10             | 50.8%               | 2026-01            | 19.8%              |                 2.57 | $1,459         | $480          |       0.3294 | 2025-10              | $2,488               | 2026-02             | $881                |                  2.82 |
| New York      |         12 | 55.5%         |        0.064 |      0.1149 | 2025-10             | 70.9%               | 2026-02            | 48.3%              |                 1.47 | $2,603         | $331          |       0.1272 | 2025-10              | $3,384               | 2026-02             | $2,083              |                  1.62 |
| San Francisco |         12 | 47.9%         |        0.086 |      0.1805 | 2025-09             | 66.0%               | 2026-02            | 37.6%              |                 1.75 | $2,481         | $462          |       0.1861 | 2025-09              | $3,365               | 2026-02             | $1,790              |                  1.88 |

## Files

- Monthly metrics CSV: `results/01_market_analysis/q4_seasonality/monthly_metrics.csv`
- Per-city seasonality CSV: `results/01_market_analysis/q4_seasonality/per_city_seasonality.csv`
- Figure: `reports/figures/01_market_analysis/q4_seasonality/01_q4_monthly_demand.png`
- Figure: `reports/figures/01_market_analysis/q4_seasonality/02_q4_monthly_revenue.png`
- Figure: `reports/figures/01_market_analysis/q4_seasonality/03_q4_seasonality_strength.png`
