# `results/05_investment_decision/` — Investment Decision Questions

Outputs that synthesise everything else into the **Investment Decision
Questions** in the TP brief — the prescriptive method (TP Section 4):

- Given a $500K budget, what is the optimal property configuration and where?
- What is the projected annual revenue under different scenarios
  (conservative, moderate, optimistic)?
- What are the biggest risks (regulatory, seasonal, competitive) and what
  does the data say about each?
- If the client could buy two properties instead of one, how should they
  diversify across cities or property types?

## Suggested artefacts

| File | Produced by | Describes |
| --- | --- | --- |
| `target_property_profile.csv` | prescriptive script | Recommended property: city, neighborhood, room type, bedrooms, target ADR, key amenities. |
| `revenue_scenarios.csv` | prescriptive script | Conservative / moderate / optimistic annual revenue with assumptions (price, occupancy, seasonality multiplier). |
| `risk_register.csv` | TBD | Risk name, likelihood, impact, evidence in the data, mitigation. |
| `two_property_diversification.csv` | TBD | Two-property bundle option, expected joint revenue, correlation analysis between cities / segments. |
| `final_revenue_table.csv` | prescriptive script | One-page summary feeding the executive summary of the memo. |

## Conventions

- Every revenue figure must be expressible as `Price × Occupancy × 365` with
  the inputs cited from `03_pricing_models/` (price), the calendar /
  reviews-based proxies (occupancy), and `01_market_analysis/` (seasonality
  multiplier when used).
- Scenarios are documented with explicit assumptions (e.g. "moderate =
  cluster median ADR × cluster mean occupancy").
- Final files reference the upstream artefact paths so the memo is
  reproducible end-to-end.
