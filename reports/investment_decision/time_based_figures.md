# Time-Based Calendar Figures

## Data Used

- Monthly occupancy comes from `data/processed/calendars/calendar_all_cleaned.csv` through `data/processed/investment_decision/step4_calendar_city_month_metrics.csv`.
- This keeps time-based risk separate from `master_data.csv`, which is listing-level and annualized.

## Figures Created

- `reports/figures/05_investment_decision/step4_monthly_occupancy_by_city.png`: monthly occupancy rate for each city.
- `reports/figures/05_investment_decision/step4_monthly_occupancy_index_by_city.png`: each city's monthly occupancy indexed to its own average.

## Seasonality Summary

- Nashville: average occupancy 33.0%, peak-to-trough gap 37.0%, coefficient of variation 0.35.
- Los Angeles: average occupancy 43.2%, peak-to-trough gap 30.1%, coefficient of variation 0.22.
- Hawaii: average occupancy 37.6%, peak-to-trough gap 28.4%, coefficient of variation 0.23.
- San Francisco: average occupancy 47.9%, peak-to-trough gap 28.4%, coefficient of variation 0.18.
- New York: average occupancy 56.3%, peak-to-trough gap 22.6%, coefficient of variation 0.12.

## Interpretation

These time-based graphs support the risk section by showing whether revenue exposure is stable year-round or concentrated in high-demand months. The indexed chart is useful because it compares each city against its own baseline, making seasonal swings easier to compare across markets with different average occupancy levels.
