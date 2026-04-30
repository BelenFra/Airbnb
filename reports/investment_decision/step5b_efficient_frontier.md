# Step 5B: Efficient Frontier Extension

## Purpose

This extension turns the Step 5 portfolio table into a simple efficient frontier. A portfolio is on the frontier if no other portfolio has both lower or equal risk and higher or equal revenue.

## Assumptions and Constraints

- Return is measured as combined moderate annual operating revenue.
- Risk is the Step 5 composite portfolio risk score.
- This is not a finance-grade mean-variance frontier because acquisition cost, expenses, and true return variance are unavailable.
- The frontier is still useful as a decision-support visualization for revenue-risk tradeoffs.

## Files Created

- `results/investment_decision/step5b_efficient_frontier_portfolios.csv`
- `reports/figures/step5b_efficient_frontier.png`

## Key Frontier Options

- Lowest-risk frontier portfolio: New York / Fort Hamilton / Entire rental unit / 0BR + Los Angeles / Culver City / Entire home / 2BR. Revenue $78,795, risk 0.00.
- Highest-revenue frontier portfolio: Los Angeles / Hollywood Hills West / Entire home / 2BR + Los Angeles / Hollywood Hills / Entire home / 2BR. Revenue $93,220, risk 0.84.
- Best balanced-score portfolio: Los Angeles / Hollywood Hills West / Entire home / 2BR + New York / Midtown / Entire rental unit / 0BR. Revenue $92,736, risk 0.24.

## Business Interpretation

The efficient frontier helps explain the tradeoff between maximizing revenue and controlling risk. The final recommendation should generally come from the frontier, because dominated portfolios give up revenue without reducing risk, or take on more risk without improving revenue.
