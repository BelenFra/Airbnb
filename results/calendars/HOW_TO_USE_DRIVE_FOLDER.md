# How to Use This Drive Folder (`Term Project / cleaned_calendars/`)

This Drive folder mirrors the layout of the GitHub repo, so you can drop it straight into your local clone and start working.

## TL;DR

1. **Clone the repo + check out the calendar branch:**
   ```bash
   git clone https://github.com/BelenFra/Airbnb.git
   cd Airbnb
   git checkout feature/calendar-cleaning-yuwang
   ```
2. **Download from this Drive folder (`cleaned_calendars/`):**
   - You only need `data/` (the 13 cleaned data CSVs). Docs already ship with the repo.
   - Right-click the `data/` folder in Drive → **Download** (Drive will zip it for you).
3. **Unzip and merge into your local repo:**
   - Unzip and drag the resulting `data/` folder into your repo root.
   - Files will land at `Airbnb/data/processed/calendars/*.csv` automatically.
4. **Smoke test:**
   ```python
   import pandas as pd
   df = pd.read_csv("data/processed/calendars/all_cities_listing_occupancy.csv")
   df.groupby("city")["occupancy_rate_proxy"].mean().sort_values()
   ```
   Should print a 5-row series with means between ~0.31 and ~0.56.

## What's the Primary Deliverable?

**`data/processed/calendars/all_cities_listing_occupancy.csv`** (~16 MB, one row per listing across all 5 cities). This is what most downstream modeling should join against.

Schema:

| Column | Description |
|---|---|
| `listing_id` | Inside Airbnb listing key |
| `city` | snake_case (`hawaii`, `los_angeles`, `nashville`, `new_york`, `san_francisco`) |
| `n_days` | Total calendar rows for this listing |
| `n_days_available` | Days flagged available in calendar |
| `n_days_unavailable` | Days flagged unavailable |
| `availability_rate` | `n_days_available / n_days` |
| `occupancy_rate_proxy` | `n_days_unavailable / n_days` ⚠️ proxy — see caveats |
| `listing_price` | Nightly price joined from `listings.csv` (USD) |
| `est_annual_revenue_proxy` | `listing_price × occupancy_rate_proxy × 365` |
| `min_minimum_nights`, `max_minimum_nights` | Min/max of `minimum_nights` seen |
| `min_maximum_nights`, `max_maximum_nights` | Same for `maximum_nights` |
| `first_date`, `last_date` | Date range covered |

Full field list and caveats are in `results/calendars/calendar_dataset_README.md` (already in the repo).

## ⚠️ Important Caveat

`occupancy_rate_proxy` is computed as the **unavailability rate**. It includes days the host blocked off as well as actual bookings, so it **systematically overestimates** true occupancy. Always label downstream charts/tables with the word *proxy* and mention this caveat. Full details in `calendar_dataset_README.md` §5.

## Folder Map (this Drive folder)

```
cleaned_calendars/
├── HOW_TO_USE_DRIVE_FOLDER.md        (this file)
├── data/
│   └── processed/
│       └── calendars/
│           ├── all_cities_listing_occupancy.csv      ⭐ primary deliverable (16 MB)
│           ├── all_cities_calendar_cleaned.csv       (2.24 GB - day-level, optional)
│           ├── <city>_listing_occupancy.csv  × 5
│           ├── <city>_calendar_cleaned.csv   × 5     (144 MB ~ 839 MB each)
│           └── README.md
└── results/
    └── calendars/
        ├── calendar_dataset_README.md       (English, hand-off doc)
        ├── calendar_dataset_README_CN.md    (Chinese mirror)
        ├── calendar_cleaning_decisions.md   (English, every cleaning rule)
        ├── calendar_cleaning_decisions_CN.md (Chinese mirror)
        └── calendars_cleaning_audit.csv     (per-city audit)
```

The `results/calendars/*` files are duplicates of what's already in the repo branch — they're here just as a convenience for anyone who only has Drive access. If you cloned the repo, you can ignore the `results/` subfolder.

## What You Probably Don't Need

- `all_cities_calendar_cleaned.csv` (2.24 GB) — concatenation of the 5 city day-level files. Skip unless you specifically need a single file for time-series work.
- Day-level `<city>_calendar_cleaned.csv` files — only download if you need calendar-level granularity. The summary occupancy table is enough for most modeling.

## Reproducing the Pipeline From Scratch

If you'd rather regenerate everything yourself from the raw `calendar.csv` / `listings.csv` files in `Term Project/<City>/`:

```bash
python scripts/cleaning/calendars/run_full_calendar_cleaning.py
# or, to skip the 2.3 GB merged file:
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --no-merged-rows
```

Runtime: ~22 minutes for all 5 cities on a MacBook.

## Questions / Issues

Ping **Yu Wang** in the group chat. Open issues against the PR on GitHub if it's about code or schema.
