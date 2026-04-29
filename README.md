# MBA 706 Student Analytics Package

## What This Is

This folder is the analytics workspace for the MBA 706 term project. It contains a pre-built Python toolkit (`mba706_toolkit.py`) with every function the course requires — data loading, cleaning, visualization, clustering, classification, regression, text analytics, and model comparison. You describe what you want in plain English, and Cursor writes the code, runs it, and saves the output.

**You do not need to write code or use the terminal yourself.**

## Term Project — Airbnb Investment Analysis (5 Cities)

Group capstone for an end-to-end investment memo on a $500K Airbnb portfolio across **Hawaii, Los Angeles, Nashville, New York, and San Francisco**. Three cleaning streams feed a unified analytical pipeline that applies the six required methods (cleaning, clustering, supervised learning, kNN, text analytics, prescriptive recommendation) and produces a quantified recommendation backed by the revenue equation:

> **Annual Revenue = Nightly Price × Occupancy Rate × 365**

### Cleaning Pipelines (one per data stream)

| Stream | Code | Listing-level output |
|---|---|---|
| **Calendar** | `scripts/cleaning/calendars/run_full_calendar_cleaning.py` | `data/processed/calendars/all_cities_listing_occupancy.csv` |
| **Listings** | `scripts/cleaning/listing/listing_by_city_cleaning.py` | `data/processed/listing/listing_by_city_cleaned.csv` |
| **Reviews** | `scripts/cleaning/reviews/run_full_review_cleaning.py` | per-city cleaned files in `data/processed/reviews/` (listing-level features rollup TBD) |

> Verify each output exists in `data/processed/` before joining. Day-level files and merged multi-GB tables are kept off the repo (see `.gitignore`) and shared via the team Drive.

### Calendar Pipeline (canonical reference)

`scripts/cleaning/calendars/run_full_calendar_cleaning.py` runs a single streaming pass per city (chunked at 200,000 rows so files up to 622 MB never have to load fully into memory). Each chunk goes through:

1. **Project columns** — keep only `listing_id, date, available, price, adjusted_price, minimum_nights, maximum_nights`.
2. **Deduplicate** — hash the seven columns and globally drop duplicate rows, keeping the first occurrence.
3. **Drop rows missing required fields** — `listing_id`, `date`, or `available` cannot be null.
4. **Parse dates** — coerce to `pd.Timestamp` and emit `YYYY-MM-DD` strings; drop unparseable rows.
5. **Normalize `available`** — map `t/true/1 → True`, `f/false/0 → False`; drop other values.
6. **Clean prices** — strip `$`, `,`, and whitespace from `price` / `adjusted_price` and cast to `float`. (Inside Airbnb's recent calendar dumps no longer carry per-night prices, so this column is empty in practice — see step 11.)
7. **Outlier clipping (no row drops)** — set `price > $10,000` to `NaN`; clip `minimum_nights` and `maximum_nights` to `[1, 1125]`.
8. **Tag the city** — add a `city` column using a snake_case mapping (`hawaii / los_angeles / nashville / new_york / san_francisco`).
9. **Aggregate per listing in-flight** — accumulate `n_days`, `n_days_available`, `n_days_unavailable`, price stats by availability flag, plus min/max night thresholds via chunkwise `groupby` + `add` / `min` / `max` reductions.
10. **Write outputs** — append the cleaned chunk to `data/processed/calendars/<city>_calendar_cleaned.csv` and (optionally) to the merged `all_cities_calendar_cleaned.csv`.
11. **Post-pass per city** — derive `availability_rate`, `unavailability_rate`, and `occupancy_rate_proxy = unavailability_rate`; **join `listing_price` from `listings.csv` for the same city** (canonical source for nightly price); compute `est_annual_revenue_proxy = listing_price × occupancy_rate_proxy × 365`; persist `data/processed/calendars/<city>_listing_occupancy.csv`.
12. **Post-pass across all cities** — concatenate the per-listing tables into `all_cities_listing_occupancy.csv` and write the per-city audit at `data/processed/calendars/calendars_cleaning_audit.csv`.

### Calendar outputs (where they go)

| File | Size (approx.) | Purpose |
| --- | ---: | --- |
| `data/processed/calendars/<city>_calendar_cleaned.csv` × 5 | 144 MB ~ 839 MB | Cleaned day-level calendar per city (gitignored) |
| `data/processed/calendars/<city>_listing_occupancy.csv` × 5 | 1 MB ~ 6 MB | Per-listing occupancy + price + revenue proxy |
| `data/processed/calendars/all_cities_calendar_cleaned.csv` | ~2.3 GB | All five cities concatenated (gitignored, optional via `--no-merged-rows`) |
| `data/processed/calendars/all_cities_listing_occupancy.csv` | 16 MB | **Primary deliverable** for downstream modeling |
| `data/processed/calendars/calendars_cleaning_audit.csv` | 2 KB | Per-city audit (rows in/out, drop reasons, occupancy summary) |

The day-level CSVs and the 2.3 GB merged file are gitignored; only the 16 MB summary table, the 2 KB audit CSV, and the documentation files travel with the repo.

### Five-city snapshot (post-clean)

| City | listings | with price | mean occupancy proxy | median listing price | median annual revenue proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| hawaii | 33,457 | 97.6% | 37.0% | $230 | $26,100 |
| los_angeles | 45,886 | 80.1% | 41.7% | $155 | $10,278 |
| nashville | 9,443 | 70.2% | 31.5% | $158 | $10,803 |
| new_york | 36,111 | 58.5% | 55.6% | $152 | $11,960 |
| san_francisco | 7,780 | 74.3% | 48.0% | $170 | $18,196 |

> **Caveat**: `occupancy_rate_proxy` equals the unavailability rate, which includes host-blocked days alongside actual bookings. It systematically overestimates true occupancy. Always label downstream results as "proxy"; see `data/processed/calendars/README.md` §5 for the full caveats.

### Reproduce (calendar)

```bash
python scripts/cleaning/calendars/run_full_calendar_cleaning.py
# Selectively:
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --cities nashville san_francisco
# Skip the 2.3 GB merged row-level file (recommended on laptops):
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --no-merged-rows
```

End-to-end runtime on a MacBook (5 cities, ~48.4 M rows): roughly 22 minutes.

### Detailed cleaning documentation

- `scripts/cleaning/calendars/calendar_cleaning_decisions.md` — every calendar cleaning rule in writing.
- `data/processed/calendars/README.md` — what to use, field definitions, join example, warnings.

## Folder Structure

| Folder / File | Purpose |
|---|---|
| `mba706_toolkit.py` | Approved analytics functions (the only library you need) |
| `AGENTS.md` | Rules for Cursor's AI (read automatically) |
| `CLAUDE.md` | Backup rules for Claude Code CLI |
| `FUNCTIONS.md` | **Quick reference** — every toolkit function on one page |
| `requirements.txt` | Python dependencies |
| `environment.yml` | Conda environment (optional) |
| `data/raw/` | Place raw Inside Airbnb files here (gitignored except READMEs) |
| `data/processed/` | Cleaned datasets + per-domain READMEs and audits |
| `notebooks/` | Notebooks for EDA and analysis |
| `scripts/cleaning/` | Cleaning scripts per data stream (calendars, listing, reviews) |
| `scripts/models/` | Modeling scripts (clustering, supervised learning, kNN) |
| `scripts/text_analysis/` | Text analytics scripts (sentiment, topic modeling) |
| `reports/` | Final deliverables (memo, slides) |
| `reports/figures/` | All plots (PNG, PDF) |
| `results/` | Analytical outputs of the memo (cluster profiles, model metrics, revenue scenarios) |

> Per-domain colocation: dataset hand-off READMEs live alongside the data they describe (`data/processed/<domain>/README.md`), and cleaning rule docs live alongside the code that implements them (`scripts/cleaning/<domain>/`). `results/` stays reserved for the analytical outputs that go into the investment memo.

## Getting Started

1. **Place raw data files** in `data/raw/`.
2. **Open this folder in Cursor.**
3. **Ask for your analysis** in the chat. Describe what you want.
4. Cursor handles environment setup, script creation, execution, and output saving.
5. **Retrieve outputs** from `results/` and `reports/figures/`.

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

Example: *"Use `data/processed/calendars/all_cities_listing_occupancy.csv`, cluster listings with k-means and an elbow plot, save the script as `scripts/models/cluster_listings.py` and the results to `results/cluster_profiles.csv`."*

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
