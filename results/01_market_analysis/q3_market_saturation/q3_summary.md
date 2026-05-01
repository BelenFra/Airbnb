# Q3 — Market saturation per city

**Question.** Which cities are most competitive (saturated)? Which have room for a new entrant?

## Method

Four facets are combined into a composite saturation score (0 = least, 1 = most saturated):

1. **Density**: listings per 10,000 residents (2024 population reference).
2. **Host HHI**: Herfindahl-Hirschman over listing share by host.
3. **% listings in multi-listing portfolios**: professional vs amateur supply.
4. **1 − mean occupancy**: low occupancy → over-supply signal.

Population sources used (state / city, 2024):

- **Hawaii**: 1,450,589
- **Los Angeles**: 3,820,914
- **Nashville**: 715,884
- **New York**: 8,335,897
- **San Francisco**: 808,988

## Headline

- Most saturated market: **Hawaii**.
- Most room for a new entrant: **San Francisco**.

> **Methodological note (occupancy).** The mean occupancy reported here uses 
> `master_data.csv` (listings with a valid price, i.e. *active* supply). The calendar
> cleaning audit reports a higher figure (e.g. NYC 56% vs 31% here) because it covers
> *every* calendar listing — including hosts who block their listing all year
> (very common in NYC under Local Law 18). For an investment decision the active-supply
> figure is the correct one; the calendar audit value is shown in the EDA only as a
> supply-utilisation metric.

## Per-city saturation table

| City          |   listings |   unique_hosts |   population_2024 |   listings_per_10k | mean_occupancy   |   host_hhi_x10k | top10_host_share   | multi_listing_host_pct   | share_listings_in_multi_host_portfolios   |   saturation_score |   saturation_rank |
|:--------------|-----------:|---------------:|------------------:|-------------------:|:-----------------|----------------:|:-------------------|:-------------------------|:------------------------------------------|-------------------:|------------------:|
| Hawaii        |      33132 |           8735 |         1,450,589 |             228.4  | 37.0%            |              28 | 11.9%              | 32.9%                    | 82.3%                                     |              0.705 |                 1 |
| Los Angeles   |      36819 |          17165 |         3,820,914 |              96.36 | 30.3%            |               6 | 4.9%               | 28.6%                    | 66.7%                                     |              0.341 |                 4 |
| Nashville     |       6634 |           3009 |           715,884 |              92.67 | 27.9%            |              31 | 13.3%              | 23.3%                    | 65.2%                                     |              0.57  |                 2 |
| New York      |      21328 |          10418 |         8,335,897 |              25.59 | 31.2%            |              38 | 13.9%              | 22.9%                    | 62.3%                                     |              0.428 |                 3 |
| San Francisco |       5795 |           2959 |           808,988 |              71.63 | 38.6%            |              29 | 12.1%              | 25.3%                    | 61.9%                                     |              0.238 |                 5 |

## Files

- Per-city saturation CSV: `results/01_market_analysis/q3_market_saturation/per_city_saturation.csv`
- Figure: `reports/figures/01_market_analysis/q3_market_saturation/01_q3_density.png`
- Figure: `reports/figures/01_market_analysis/q3_market_saturation/02_q3_host_concentration.png`
- Figure: `reports/figures/01_market_analysis/q3_market_saturation/03_q3_saturation_score.png`
