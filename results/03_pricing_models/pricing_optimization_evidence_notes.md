# Pricing optimization — Evidence appendix

**Purpose:** Key tables bundled with this upload (minimal set). Full diagnostic exports can be regenerated with **`scripts/run_descriptive_analysis.py`** (needs `master_data.csv`).

**Descriptive only — not causal.**

---

## Global price tertiles (`tables/05_price_bands_tertiles_overall.csv`)

Equal **listing-count** tertiles of nightly price (~**33%** of listings per band). Approximate tertile cuts on this sample: **P33 ≈ $132**, **P66 ≈ $250/night**.

| price_band | n | mean_price | mean_occ (nights) | mean_proxy_revenue |
|------------|---|-----------:|------------------:|-------------------:|
| Low | 34,650 | 86.26 | 83.66 | 7,702.69 |
| Mid | 34,844 | 184.28 | 82.75 | 15,010.57 |
| High | 34,213 | 1,540.36 | 50.55 | 27,189.25 |

The High band mean price is inflated by listings **above P66**, including extreme right-tail nightly rates.

---

## City summaries (`tables/03_summary_by_city.csv`)

Grouped **count**, **mean**, **median**, **std** for `price`, `estimated_occupancy_l365d`, `annual_revenue_proxy`. Open CSV for full five-metro breakout.

---

## Room type summaries (`tables/04_summary_by_room_type.csv`)

Grouped **count**, **mean**, **median**, **std** for the same measures. Interpret **hotel room** sparingly (**n ≈ 690**, heavy outliers).

---

Cross-check correlations and finer band splits: run **`run_descriptive_analysis.py`** locally if needed.
