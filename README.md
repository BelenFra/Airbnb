# MBA 706 Student Analytics Package

## What This Is

This folder is the analytics workspace for the MBA 706 term project. It contains a pre-built Python toolkit (`mba706_toolkit.py`) with every function the course requires — data loading, cleaning, visualization, clustering, classification, regression, text analytics, and model comparison. You describe what you want in plain English, and Cursor writes the code, runs it, and saves the output.

**You do not need to write code or use the terminal yourself.**

## Term Project — Airbnb Investment Analysis (5 Cities)

Group capstone for an end-to-end investment memo on a $500K Airbnb portfolio across **Hawaii, Los Angeles, Nashville, New York, and San Francisco**. Three cleaning streams feed a unified analytical pipeline that applies the six required methods (cleaning, clustering, supervised learning, kNN, text analytics, prescriptive recommendation) and produces a quantified recommendation backed by the revenue equation:

> **Annual Revenue = Nightly Price × Occupancy Rate × 365**

### Inside Airbnb snapshot dates (raw data)

The raw `listings` / `reviews` / `calendar` files in `data/raw/` were downloaded
from [insideairbnb.com/get-the-data](https://insideairbnb.com/get-the-data) in
the September–October 2025 release window. The exact snapshot date per city is:

| City | Snapshot date (Inside Airbnb) |
| --- | --- |
| Hawaii | 16 September 2025 |
| Los Angeles | 1 September 2025 |
| Nashville | 23 September 2025 |
| New York | 1 October 2025 |
| San Francisco | 1 September 2025 |

All five cities must come from the **same coordinated snapshot window**. If we
ever re-pull data we re-pull the full set; mixing snapshot quarters across
cities biases every cross-city comparison (review timeline, occupancy proxies,
yearly recovery indices). The snapshot window also caps the forward-looking
calendar at ~365 days from the snapshot date — anything beyond that is still
host availability, not actual demand.

### Cleaning Pipelines (one per data stream)

| Stream | Code | Listing-level merged output |
|---|---|---|
| **Calendar / occupation** | `scripts/cleaning/calendars/run_full_calendar_cleaning.py` (normally via orchestrator) | `data/processed/occupation_all_cleaned.csv` |
| **Listings** | `scripts/cleaning/listing/run_full_listing_cleaning.py` | `data/processed/listing_all_cleaned.csv` |
| **Reviews** | `scripts/cleaning/reviews/run_full_review_cleaning.py` | `data/processed/reviews_all_cleaned.csv` |

Per-city intermediates live under `data/processed/calendar/<city_slug>/`, `data/processed/listing/<city_slug>/`, and `data/processed/review/<city_slug>/`. The **joined modeling table** after the orchestrator is `data/processed/master_data.csv` (listings + occupation rates). Day-level calendars and merged multi-GB CSVs stay gitignored (see `.gitignore`); regenerate locally after cloning.

### Calendar pipeline (canonical reference)

`scripts/cleaning/calendars/run_full_calendar_cleaning.py` runs a streaming pass per city (chunk size 200,000 rows). Each chunk:

1. **Project columns** — `listing_id, date, available, price, adjusted_price, minimum_nights, maximum_nights`.
2. **Deduplicate** — hash the seven columns; drop duplicates keeping the first.
3. **Drop rows missing required fields** — `listing_id`, `date`, `available`.
4. **Parse dates** — `YYYY-MM-DD`; drop invalid.
5. **Normalize `available`** — map `t/true/1`, `f/false/0`; drop others.
6. **Clean numeric fields** — `price` / `adjusted_price` parsed without hard monetary caps **(recent Inside Airbnb calendars usually leave calendar price empty)**.
7. **Nights columns** — coerced where present; occupancy comes from availability, not clipped caps on price/nights (see decisions doc).
8. **City tag** — snake_case slug per city (`hawaii`, `los_angeles`, …).
9. **Per-listing aggregation in flight** — `n_days`, available/unavailable counts, min/max night stats.
10. **Row-level CSVs** (optional) — `data/processed/calendar/<slug>/calendar_<slug>_cleaned.csv` (and optionally merged `data/processed/calendar_all_cleaned.csv`).
11. **Listing-level occupancy** — `availability_rate`, `unavailability_rate`, `occupancy_rate_proxy`; **`listing_price` comes from `data/processed/listing_all_cleaned.csv`** when present; revenue proxy fields use that price layer.
12. **Merge occupation** — per-city occupation files concatenate to `data/processed/occupation_all_cleaned.csv`; audit CSV at `results/01_market_analysis/calendars/calendars_cleaning_audit.csv`.

### Calendar outputs (paths)

| File | Notes |
|---|---|
| `data/processed/calendar/<slug>/calendar_<slug>_cleaned.csv` × 5 | Day-level calendar per city (gitignored, optional) |
| `data/processed/calendar/<slug>/occupation_<slug>_cleaned.csv` × 5 | Listing-level occupancy + price join |
| `data/processed/calendar_all_cleaned.csv` | Large merged rows (optional, gitignored) |
| `data/processed/occupation_all_cleaned.csv` | Merged listing-level table for joins |
| `results/01_market_analysis/calendars/calendars_cleaning_audit.csv` | Per-city run stats |

### Five-city snapshot (post-clean)

| City | listings | with price | mean occupancy proxy | median listing price | median annual revenue proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| hawaii | 33,457 | 97.6% | 37.0% | $230 | $26,100 |
| los_angeles | 45,886 | 80.1% | 41.7% | $155 | $10,278 |
| nashville | 9,443 | 70.2% | 31.5% | $158 | $10,803 |
| new_york | 36,111 | 58.5% | 55.6% | $152 | $11,960 |
| san_francisco | 7,780 | 74.3% | 48.0% | $170 | $18,196 |

> **Caveat**: `occupancy_rate_proxy` tracks unavailability, not bookings. Treat it as a **proxy**. Full discussion: `scripts/cleaning/calendars/calendar_cleaning_decisions.md`.

### Reproduce cleaning

Prefer the orchestrator (writes listings → reviews → occupation → `master_data`):

```powershell
python scripts\cleaning\run_cleaning_pipeline.py
```

Calendar only (advanced):

```bash
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --occupation-only --no-merged-rows
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --cities nashville san_francisco --occupation-only
```

Rough runtime (5 cities raw calendars): ~20–25 minutes on a laptop class machine.

### Detailed cleaning documentation

- `scripts/cleaning/calendars/calendar_cleaning_decisions.md` — calendar-specific rules.
- `scripts/cleaning/listing/listing_cleaning_decisions.md` — listing dtypes and null-fill logic.
- `AGENTS.md` — pipeline order and authoritative path layout.

## Folder Structure

| Folder / File | Purpose |
|---|---|
| `mba706_toolkit.py` | Approved analytics functions (the only library you need) |
| `AGENTS.md` | Rules for Cursor's AI (read automatically) |
| `CLAUDE.md` | Backup rules for Claude Code CLI (delegates to `AGENTS.md`) |
| `FUNCTIONS.md` | **Quick reference** — every toolkit function on one page |
| `requirements.txt` | Python dependencies |
| `environment.yml` | Conda environment (optional) |
| `data/raw/` | Place raw Inside Airbnb files here (gitignored; only READMEs tracked) |
| `data/processed/` | Cleaned outputs from the pipeline (multi-GB CSVs gitignored — regenerate after clone) |
| `notebooks/` | Notebooks for EDA and analysis |
| `scripts/cleaning/` | Cleaning scripts per data stream (calendars, listing, reviews) + orchestrator |
| `scripts/eda/` | EDA inventory scripts for raw and processed data |
| `scripts/market_analysis/` | Q1–Q4 market-level analysis scripts (risk-adjusted revenue, price/occupancy/revenue, saturation, seasonality) |
| `scripts/models/` | Modeling scripts (clustering, supervised learning, kNN) |
| `scripts/text_analysis/` | Text analytics: TF–IDF pipeline, sentiment, methodology (`text_analytics_readme.md`) |
| `reports/` | Final deliverables (memo, slides) |
| `reports/figures/` | All plots (PNG, PDF) — see `reports/figures/market_analysis/` for Q1–Q4 charts |
| `results/` | Analytical outputs organised by **business question** (`01_market_analysis/`, `02_segmentation/`, `03_pricing_models/`, `04_guest_experience/`, `05_investment_decision/`). Cleaning audits live inside `01_market_analysis/` (per-asset subfolders: `01_market_analysis/listing/`, `01_market_analysis/calendars/`, `01_market_analysis/reviews/`). See `results/README.md`. |

> Cleaning rules and dataset layout are documented alongside code (`scripts/cleaning/*/README*.md`) and `AGENTS.md`; large derived CSV folders under `data/processed/` are gitignored except what you regenerate locally after cloning.

## Cleaning Pipeline Order

To clean the Airbnb raw data, run the orchestrator:

```powershell
python scripts\cleaning\run_cleaning_pipeline.py
```

Do not run the individual listing, review, or calendar cleaning scripts manually unless debugging. The orchestrator manages dependencies and writes the standardized outputs.

Execution order:
1. **Listings**: creates `data/processed/listing_all_cleaned.csv`.
2. **Reviews**: creates `data/processed/reviews_all_cleaned.csv`.
3. **Calendar occupation**: uses `data/processed/listing_all_cleaned.csv` and creates `data/processed/occupation_all_cleaned.csv`.
4. **Final join**: joins listings with occupation rates and creates `data/processed/master_data.csv`.

> **Important — Q4 (seasonality) needs row-level calendars.** The default
> orchestrator runs with `--occupation-only` which is fast but does *not* write
> the row-level calendar files needed for Q4. To generate the full project
> dataset (including `data/processed/calendar_all_cleaned.csv`, ~3 GB) run:
>
> ```bash
> python scripts/cleaning/run_cleaning_pipeline.py --calendar-write-row-files
> ```
>
> See `AGENTS.md` for details.

## Market-Level Analysis (Q1–Q4)

The four market-level questions of the term project are answered by the scripts
under `scripts/market_analysis/`:

| Q | Question | Script | Outputs |
|---|---|---|---|
| Q1 | Best risk-adjusted revenue opportunity | `scripts/market_analysis/q1_risk_adjusted_revenue.py` | `results/01_market_analysis/q1_risk_adjusted_revenue/`, `reports/figures/market_analysis/q1_risk_adjusted_revenue/` |
| Q2 | Price, occupancy, revenue comparison | `scripts/market_analysis/q2_price_occupancy_revenue.py` | `results/01_market_analysis/q2_price_occupancy_revenue/`, `reports/figures/market_analysis/q2_price_occupancy_revenue/` |
| Q3 | Market saturation / room for new entrants | `scripts/market_analysis/q3_market_saturation.py` | `results/01_market_analysis/q3_market_saturation/`, `reports/figures/market_analysis/q3_market_saturation/` |
| Q4 | Seasonality of demand and revenue | `scripts/market_analysis/q4_seasonality.py` | `results/01_market_analysis/q4_seasonality/`, `reports/figures/market_analysis/q4_seasonality/` |

All four scripts read from `data/processed/master_data.csv`; Q4 additionally
streams `data/processed/calendar_all_cleaned.csv` in chunks. Each script writes
a `q<i>_summary.md` memo with metrics, plots, and business interpretation.

## Getting Started

1. **Place raw data files** in `data/raw/`.
2. **Open this folder in Cursor.**
3. **Ask for your analysis** in the chat. Describe the data file, analysis goal, target variable if relevant, and desired outputs.
4. Cursor handles everything: environment setup, script creation, execution, and output saving.
5. **Retrieve your outputs** from `results/` and `reports/figures/`.

## What Happens Automatically

When you start a session, Cursor will:
1. Check if Python packages are installed; install them if missing.
2. Run `scripts/check_environment.py` and report PASS/FAIL.
3. Attempt automatic repair if anything fails.
4. Proceed with the requested analysis.
5. Never ask you to run terminal commands yourself.

## How to Ask for an Analysis

Mention three things in your prompt:
1. **Data file** — `data/raw/<filename>` or `data/processed/<filename>`
2. **Analysis** — what you want done
3. **Output names** — script in `scripts/`, results in `results/` and/or `reports/figures/`

Example — course-style classification: *"Use `data/raw/churn.csv`, train logistic regression, random forest, and boosted trees on target `Churn`, compare models, save script as `scripts/churn_models.py` and results to `results/churn_comparison.xlsx`."*

Example — Airbnb term project modeling: *"Use `data/processed/master_data.csv`, cluster listings with k-means and save an elbow plot; save the script as `scripts/models/cluster_listings.py` and results to `results/cluster_profiles.csv`."*

Same pattern for every request: dataset path (`data/raw/...` after cleaning pipeline, or processed outputs), analytic goal (+ target if supervised), script name under `scripts/`, and deliverables under `results/` / `reports/figures/`.

## If the Toolkit Doesn't Have a Function You Need

Cursor will ask you:
> "The toolkit does not include [function_name]. Do you want me to add it to `mba706_toolkit.py` and then run the analysis?"

Approve or decline before it proceeds.

## Output Formats

| Format | Saved to |
|---|---|
| `.py` scripts | `scripts/` |
| `.xlsx`, `.csv`, `.docx`, `.txt`, `.pdf` | `results/` |
| `.png`, `.pdf` plots | `reports/figures/` |

## Troubleshooting

| Problem | What Happens |
|---|---|
| Missing packages | Cursor installs them via `pip install -r requirements.txt` |
| Excel file not found | Verify file is in `data/raw/` and sheet name is correct |
| Missing toolkit function | Approve function addition, then Cursor reruns |
| xgboost error | Cursor attempts repair; if native fails, toolkit fallback runs automatically |
| OpenMP / SHM error | Already handled by built-in safety guards |

## Cross-Platform Support

- Works on both **macOS** and **Windows**.
- `xgboost` is supported with automatic fallback: if native xgboost fails (e.g., OpenMP issues), the toolkit seamlessly falls back to sklearn GradientBoosting.
- All scripts include OpenMP safety guards to prevent shared-memory crashes.

## Windows-Specific Notes

- If using PowerShell, you may need to run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once.
- If Conda is used, run `conda init powershell` once, then restart the terminal.
- All toolkit paths use cross-platform `pathlib`, so no path separator issues.

## Instructor Setup (Optional)

For pre-configuring lab machines:
```bash
# Option A: Conda
conda env create -f environment.yml
conda activate mba706
python scripts/check_environment.py

# Option B: pip only
pip install -r requirements.txt
python scripts/check_environment.py
```
