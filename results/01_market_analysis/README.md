# `results/01_market_analysis/` — Market-Level Questions

Outputs that answer the **Market-Level Questions** in the TP brief:

- Which city offers the best risk-adjusted revenue opportunity?
- How do average nightly prices, occupancy rates, and estimated annual
  revenues compare across the five cities?
- Which cities have the most competitive (saturated) markets? Which have
  room for a new entrant?
- How does seasonality affect revenue in each city? Is demand stable
  year-round or concentrated in peak months?

## Suggested artefacts

| File | Produced by | Describes |
| --- | --- | --- |
| `city_revenue_potential.csv` | TBD | Per-city ADR × occupancy × 365 with confidence band. |
| `seasonality_by_city.csv` | TBD | Monthly demand share + peak/trough ratio per city (post-cleaning). |
| `recovery_indexed_2019.csv` | TBD | Year-over-year recovery indexed to 2019 = 100 (reviews + bookings). |
| `competitive_saturation.csv` | TBD | Listings per population / per tourist arrival, supply-vs-demand gap. |
| `risk_adjusted_revenue.csv` | TBD | Mean / std-dev of monthly revenue → Sharpe-like ratio per city. |

## Conventions

- City tokens use the project-wide snake_case slugs.
- Currency in USD, occupancy in 0-1 fraction.
- Revenue figures are documented as either *posted ADR* or *realised ADR* in
  the file's first row of comments (`# notes: ...`) when relevant.
