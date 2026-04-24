# MBA 706 Analytics Toolkit — Rules for Cursor

You are helping an MBA student run data analytics in Cursor using an approved toolkit.

## Critical Rules

1. **Toolkit only.** Use ONLY functions from `mba706_toolkit.py`. Never write raw scikit-learn, pandas plotting, or matplotlib code directly when a toolkit function exists.
2. **No custom splits.** Always use `split_data()` — never create train/test splits manually.
3. **Reproducibility.** Always use `RANDOM_STATE = 42`.
4. **Scripts, not snippets.** Write analysis code as a `.py` script inside the proper folder in `scripts/`(example. scripts/cleaning/), then run it.
5. **File discipline.** 
    Read data from `data/raw` or `data/processed/`. 
    Save plots (PNG/PDF) to `reports/figures/`. 
    Save final reports (PDF/DOCX) in `reports/` 
    Save intermediate results (CSV/EXCEL) in `data/processed/`
    Save everything else (Excel/CSV/DOCX/TXT) to `results/`.
6. **Business first.** Provide business interpretation after every analysis, not just metrics.
7. **Ask before extending.** If a needed function does not exist in the toolkit, ask the student before adding it.
8. **No manual terminal.** Students will NOT run terminal commands. You must run all commands yourself.

## When to Use `execute_python_code()`

The `execute_python_code()` function is an escape hatch for tasks the toolkit doesn't cover (e.g., a custom visualization type, a one-off data transformation). Use it only when no toolkit function exists and the student has approved. Do not use it to bypass toolkit wrappers for standard tasks like model training or splitting.

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

## Data Loader Rules

- `.xlsx` / `.xls` files → `load_excel_data()`
- `.csv` files → `load_data()`

## Before Writing Any Analysis Script, Confirm

- Which `data/<file>` (and sheet name if Excel)
- Target variable (if supervised learning)
- Script filename in `scripts/`
- Output files to generate in `results/` and/or `plots/`

## XGBoost Behavior

- `train_xgboost()` automatically probes whether native xgboost is safe.
- If unsafe, it falls back to sklearn GradientBoosting and returns `status=success` with `backend=sklearn_gradient_boosting_fallback`.
- Always report which backend was used in results/interpretation.

## Standard Workflow

1. `load_data()` or `load_excel_data()`
2. `get_column_info()` / `get_summary_statistics()`
3. `clean_data()`
4. `create_visualization()`
5. `split_data()` (before any modeling)
6. `train_*()` (one or more models)
7. `evaluate_classifier_performance()` / `compare_models()`
8. Save deliverables to `results/` and `plots/`

## Cross-Platform Notes

- Avoid hardcoded OS-specific paths (no `/tmp/...` or `C:\...`).
- Use project-relative paths via `PROJECT_ROOT`.
- Do not rely on interactive plot windows; save plots to files.
- The toolkit handles path resolution internally via `_TOOLKIT_ROOT`.
