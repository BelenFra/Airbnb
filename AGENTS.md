# MBA 706 Analytics Toolkit — Rules for Cursor

You are helping an MBA student run data analytics in Cursor. The repo ships an analytics toolkit (`mba706_toolkit.py`) that wraps common tasks (loading, cleaning, splits, training, plotting). Use it where it helps, but it is **not** mandatory: when the toolkit does not cover the task or a teammate's PR uses pandas / scikit-learn / matplotlib directly, that is also acceptable as long as the rest of these rules (paths, reproducibility, business interpretation) are respected.

## Critical Rules

1. **Reproducibility.** Always use `RANDOM_STATE = 42` for any stochastic step.
2. **Scripts, not snippets.** Write analysis code as a `.py` script inside the proper folder in `scripts/` (example: `scripts/cleaning/`), then run it.
3. **File discipline.**
    Read data from `data/raw` or `data/processed/`.
    Save plots (PNG/PDF) to `reports/figures/`.
    Save final reports (PDF/DOCX) in `reports/`.
    Save cleaned datasets (CSV/EXCEL) in `data/processed/` following the **Cleaning Pipeline Outputs** layout below.
    Save everything else (Excel/CSV/DOCX/TXT) to `results/`, organised by **business question** (`01_market_analysis/`, `02_segmentation/`, `03_pricing_models/`, `04_guest_experience/`, `05_investment_decision/`). Cleaning audits live inside `01_market_analysis/` per-asset family (`01_market_analysis/listing/`, `01_market_analysis/calendars/`, `01_market_analysis/reviews/`). Analytical outputs (cluster profiles, model metrics, revenue scenarios) go to the matching business-question folder.
4. **Business first.** Provide business interpretation after every analysis, not just metrics.
5. **Ask before extending the toolkit.** If you do choose to add a new function to `mba706_toolkit.py`, ask the student first.
6. **No manual terminal.** Students will NOT run terminal commands. You must run all commands yourself.

## Environment Setup (Automatic)

At the start of every session:
1. Run `python scripts/check_environment.py` and report PASS/FAIL.
2. If it fails, attempt automatic repair (pip install), then re-run.
3. If native xgboost still fails after repair, continue without blocking — `train_xgboost()` has a built-in sklearn fallback.
4. Save diagnostics to `results/environment_check.txt` when warnings/failures occur.

If the required Python packages are not installed at all:
```
pip install -r requirements.txt
```
Then re-run `scripts/check_environment.py`.

## Script Bootstrap (Required at Top of Every Script)

```python
import os
import sys
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_USE_SHM"] = "0"
os.environ["MPLCONFIGDIR"] = ".cache/matplotlib"
os.environ["XDG_CACHE_HOME"] = ".cache"
os.environ["MPLBACKEND"] = "Agg"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
```

`parents[1]` is correct for scripts directly under `scripts/`. For nested scripts use the depth that resolves to the project root:

- `scripts/cleaning/<asset>/run_full_<asset>_cleaning.py` → `parents[3]`
- `scripts/cleaning/run_cleaning_pipeline.py` → `parents[2]`
- `scripts/models/text_analysis/*.py` → `parents[3]`

## Data Loader Rules

- `.xlsx` / `.xls` files → `load_excel_data()`
- `.csv` files → `load_data()`

## Cleaning Pipeline Outputs

The cleaning pipeline (`scripts/cleaning/run_cleaning_pipeline.py`) is the single source of truth for cleaned-data locations. Every cleaning script must write to the paths below and nowhere else.

### Cleaning Execution Order

Run cleaning through the orchestrator:

```powershell
python scripts\cleaning\run_cleaning_pipeline.py --calendar-write-row-files
```

Do not run the individual listing, review, or calendar cleaning scripts manually unless debugging a specific step. The orchestrator must manage dependencies in this order:

1. **Listings first**: creates `data/processed/listing_all_cleaned.csv`.
2. **Reviews second**: creates `data/processed/reviews_all_cleaned.csv`.
3. **Calendar occupation third**: uses `data/processed/listing_all_cleaned.csv` and creates `data/processed/occupation_all_cleaned.csv`.
4. **Final join last**: joins `listing_all_cleaned.csv` with `occupation_all_cleaned.csv` and creates `data/processed/master_data.csv`.

**Listing revenue integrity (Prof. Emadi):** Do not carry listings with **null or empty `price`** into the merged listing master used for revenue logic (`price × occupancy × 365` style joins). The listing cleaner **drops** those rows after merge (`scripts/cleaning/listing/run_full_listing_cleaning.py`); downstream scripts assume non-null `price` where the revenue equation applies.

#### Why `--calendar-write-row-files` is mandatory for the term project

The Q4 *seasonality* analysis (`scripts/market_analysis/q4_seasonality.py`) needs the **row-level** calendar (one row per listing × date) to aggregate demand by `(city, year_month)`. Without the flag the orchestrator only writes the per-listing occupation table, and Q4 cannot run. Always call the orchestrator with `--calendar-write-row-files` so the project ships:

- `data/processed/calendar/<city>/calendar_<city>_cleaned.csv`
- `data/processed/calendar_all_cleaned.csv` (~3 GB, used by Q4)

If you need to skip the row-level dump for a quick smoke test, use `--occupation-only` and document it explicitly — do **not** ship cleaned outputs from an `--occupation-only` run as the final processed dataset.

| Asset | Per-city cleaned file | Merged cleaned file |
|---|---|---|
| Listings | `data/processed/listing/<city_slug>/listing_<city_slug>_cleaned.csv` | `data/processed/listing_all_cleaned.csv` |
| Reviews  | `data/processed/review/<city_slug>/reviews_<city_slug>_cleaned.csv` | `data/processed/reviews_all_cleaned.csv` |
| Calendar (row-level, optional) | `data/processed/calendar/<city_slug>/calendar_<city_slug>_cleaned.csv` | `data/processed/calendar_all_cleaned.csv` |
| Calendar occupation | `data/processed/calendar/<city_slug>/occupation_<city_slug>_cleaned.csv` | `data/processed/occupation_all_cleaned.csv` |
| Final join (listings + occupation) | — | `data/processed/master_data.csv` |

Audits and human-readable summaries live under `results/01_market_analysis/<asset_family>/`:

- `results/01_market_analysis/listing/listing_by_city_cleaning_summary.txt`
- `results/01_market_analysis/calendars/calendars_cleaning_audit.csv`
- `results/01_market_analysis/reviews/reviews_cleaning_audit.csv`

City slugs are lowercase snake_case (`hawaii`, `los_angeles`, `nashville`, `new_york`, `san_francisco`). Do not invent new locations or rename these files; if a new asset family is added, extend this table first.

## Text analytics & text mining (Unstructured Data)

**MBA706 / Kenan–Flagler unstructured-data sequence:** **normalization** → **stemming** → **TF–IDF** weighting (implementation detail and governance in §3–§4 of `scripts/models/text_analysis/text_analytics_readme.md`).

Governance and definitions (**Document** = listing-level text unit; **Corpus** = city/market collection; **BoW**; TF–IDF formula \(\mathrm{TFIDF}(t,d)=\mathrm{TF}(t,d)\times\mathrm{IDF}(t)\)) live in **`scripts/models/text_analysis/text_analytics_readme.md`**. Follow that document for methodology and outputs.

### Rules

1. **Inputs:** Use `data/processed/reviews_all_cleaned.csv` (canonical) or **`data/processed/all_reviews_cleaned.csv`** if present as an alias; join listing→city from **`data/processed/master_data.csv`** (`id`, `City`).
2. **Toolkit:** Use `load_data()` / `load_excel_data()` for routine CSV loads. Hierarchical TF–IDF (one matrix per **listing** as document + one matrix for **city**-level corpora) is **not** implemented in `create_tfidf_features()`; use **`scripts/models/text_analysis/run_hierarchical_text_mining.py`**, which applies scikit-learn `TfidfVectorizer` with the preprocessing/stemming described in the text-analytics README (approved project pattern for this deliverable).
3. **Chunked reads:** The merged reviews file can be multi-GB. **Streaming / chunked `pandas.read_csv`** for aggregation by `listing_id` is allowed and required when the full file does not fit in memory.
4. **Outputs:** Save hierarchical text-mining artefacts (sparse matrices `.npz`, vocabularies `.json`, row indices, structured CSVs) under **`results/04_guest_experience/text_features/`** (see README there and in `scripts/models/text_analysis/text_analytics_readme.md`). Other guest-experience memo tables stay in **`results/04_guest_experience/`** as needed.
5. **Reproducibility:** `RANDOM_STATE = 42` for any stochastic step (e.g. sampling listings via `--max-listings`).

## Before Writing Any Analysis Script, Confirm

- Which `data/<file>` (and sheet name if Excel)
- Target variable (if supervised learning)
- Script filename in `scripts/`
- Output files to generate in `results/` and/or `reports/figures/`

## XGBoost Behavior

- `train_xgboost()` automatically probes whether native xgboost is safe.
- If unsafe, it falls back to sklearn GradientBoosting and returns `status=success` with `backend=sklearn_gradient_boosting_fallback`.
- Always report which backend was used in results/interpretation.

## Standard Workflow (toolkit reference)

The toolkit provides a "happy path" for course-style tasks. Use it as a checklist when convenient — feel free to drop to plain pandas / scikit-learn / matplotlib when a step is more naturally written that way.

1. `load_data()` or `load_excel_data()` — or `pandas.read_csv` / `read_excel` directly when chunked / streaming reads are needed.
2. `get_column_info()` / `get_summary_statistics()`.
3. `clean_data()`.
4. `create_visualization()` — or `matplotlib` / `seaborn` directly for custom charts.
5. `split_data()` (before any modeling) — keeps the 70/15/15 split + `RANDOM_STATE = 42` consistent across blocks.
6. `train_*()` (one or more models) — or `sklearn` estimators directly.
7. `evaluate_classifier_performance()` / `compare_models()`.
8. Save deliverables to `results/` and `reports/figures/`.

## Cross-Platform Notes

- Avoid hardcoded OS-specific paths (no `/tmp/...` or `C:\...`).
- Use project-relative paths via `PROJECT_ROOT`.
- Do not rely on interactive plot windows; save plots to files.
- The toolkit handles path resolution internally via `_TOOLKIT_ROOT`.
