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

- Lowest-risk frontier portfolio: Los Angeles / Echo Park / Entire home / 2BR + Hawaii / North Shore Kauai / Entire rental unit / 0BR. Revenue $83,036, risk 0.00.
- Highest-revenue frontier portfolio: Los Angeles / Avalon / Entire condo / 2BR + Los Angeles / Avalon / Entire home / 2BR. Revenue $209,748, risk 0.83.
- Best balanced-score portfolio: Los Angeles / Avalon / Entire condo / 2BR + Hawaii / North Kona / Entire serviced apartment / 1BR. Revenue $189,886, risk 0.18.

## Business Interpretation

The efficient frontier helps explain the tradeoff between maximizing revenue and controlling risk. The final recommendation should generally come from the frontier, because dominated portfolios give up revenue without reducing risk, or take on more risk without improving revenue.
