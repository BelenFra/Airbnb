# MBA 706 Student Analytics Package

## What This Is

This folder is your analytics workspace for Cursor. It contains a pre-built Python toolkit (`mba706_toolkit.py`) with every function you need for the course — data loading, cleaning, visualization, clustering, classification, regression, text analytics, and model comparison. You describe what you want in plain English, and Cursor writes the code, runs it, and saves the output.

**You do not need to write code or use the terminal yourself.**

## Folder Structure

| Folder / File | Purpose |
|---|---|
| `mba706_toolkit.py` | Approved analytics functions (the only library you need) |
| `AGENTS.md` | Rules for Cursor's AI (read automatically — you don't need to touch this) |
| `CLAUDE.md` | Backup rules for Claude Code CLI (you don't need to read this) |
| `FUNCTIONS.md` | **Quick reference** — every toolkit function on one page |
| `requirements.txt` | Python dependencies |
| `environment.yml` | Conda environment (optional, for instructor pre-setup) |
| `data/raw` | **Place your datasets here** |
| `data/processed` | clean csv files and Master_Data.csv final|
| `notebooks/` | Noteooks for EDA Exploratory Data analysis|
| `scripts/cleaning/` | All generated cleaning scripts |
| `scripts/models/` | Clustering, Supervised Learning y k-NN |
| `scripts/text_analysis/` | Clustering, Supervised Learning y k-NN |
| `reports` | Final Deliverables (Memo and reports) |
| `reports/figures/` | All plots and images (PNG, PDF) |
| `results/` | All other outputs |

## Getting Started

1. **Place your data file(s)** in the `data/` folder.
2. **Open this folder in Cursor.**
3. **Ask for your analysis** in the chat. See `prompt_examples/` for templates, or just describe what you want.
4. Cursor handles everything: environment setup, script creation, execution, and output saving.
5. **Retrieve your outputs** from `results/` and `plots/`.

## What Happens Automatically

When you start a session, Cursor will:
1. Check if Python packages are installed; install them if missing.
2. Run `scripts/check_environment.py` and report PASS/FAIL.
3. Attempt automatic repair if anything fails.
4. Proceed with your requested analysis.
5. Never ask you to run terminal commands yourself.

## Where to Put Datasets

Always place input data files in `data/raw`. Reference them as:
- `data/raw/my_data.csv`
- `data/raw/my_data.xlsx`

## How to Ask for an Analysis

Mention three things in your prompt:
1. **Data file** — `data/<filename>`
2. **Analysis** — what you want done
3. **Output names** — script in `scripts/`, results in `results/` and/or `plots/`

Example: *"Use `data/churn.csv`, train logistic regression, random forest, and boosted trees on target `Churn`, compare models, save script as `scripts/churn_models.py` and results to `results/churn_comparison.xlsx`."*

See `prompt_examples/` for more examples organized by analysis type.

## If the Toolkit Doesn't Have a Function You Need

Cursor will ask you:
> "The toolkit does not include [function_name]. Do you want me to add it to `mba706_toolkit.py` and then run the analysis?"

Approve or decline before it proceeds.

## Output Formats

| Format | Saved to |
|---|---|
| `.py` scripts | `scripts/` |
| `.xlsx`, `.csv`, `.docx`, `.txt`, `.pdf` | `results/` |
| `.png`, `.pdf` plots | `plots/` |

## Troubleshooting

| Problem | What Happens |
|---|---|
| Missing packages | Cursor installs them via `pip install -r requirements.txt` |
| Excel file not found | Verify file is in `data/` and sheet name is correct |
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
