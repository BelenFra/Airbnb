# Listing Cleaning Logic

This folder contains the cleaning logic for raw Airbnb `listings.csv` files. The EDA notebook is no longer used to execute this script or create pipeline inputs; it only profiles the raw listing data. Pipeline execution is handled by `scripts/cleaning/run_cleaning_pipeline.py`.

## Entry Point

Run listing cleaning through the project pipeline:

```powershell
python scripts\cleaning\run_cleaning_pipeline.py --skip-reviews --skip-calendars
```

The listing-specific script is:

```powershell
python scripts\cleaning\listing\run_full_listing_cleaning.py --phase all
```

## Source Data

The script reads each city file from:

```text
data/raw/<City>/listings.csv
```

It processes the five city folders used in the project:

- `Hawaii`
- `Los Angeles`
- `Nashville`
- `New York`
- `San Francisco`

## Missing Value Definition

The listing cleaner treats these text values as missing:

- empty string after trimming whitespace
- `nan`
- `None`

This same definition is used before dtype coercion and before null replacement.

## Phase 1: Merge City Listings

The merge phase:

1. Loads each raw city `listings.csv`.
2. Applies standardized dtype coercion using the rules in `run_full_listing_cleaning.py` documented here. The script does not depend on an EDA-generated dtype CSV.
3. Keeps only columns shared across all city listing files.
4. Drops `license` and `calendar_updated`.
5. Adds a `City` column using the source folder name.
6. Removes rows where `price` is missing or empty.
7. Writes listing merge audit results to `results/listing/listing_by_city_cleaning_summary.txt`.

Latest audit summary:

- Initial observations across all city listing files: `132,677`
- Initial raw union columns: `79`
- Columns removed because they were not shared across cities: `0`
- Explicit columns removed: `license`, `calendar_updated`
- Rows removed because `price` was null or empty: `28,969`
- Final observations after merge phase: `103,708`
- Final columns after merge phase: `78`

## Phase 2: Replace Listing Nulls

The null replacement phase applies the explicit business rules in `LISTING_NULL_ACTIONS` inside `run_full_listing_cleaning.py`. This dictionary is the only source of null rules; EDA artifacts do not influence cleaning behavior.

Core rules:

- `price`: remove empty rows, never impute price.
- Text fields such as `description`, `neighborhood_overview`, `host_about`, and `bathrooms_text`: replace missing values with `unknown`.
- Rate/count/score fields such as `host_response_rate`, `host_acceptance_rate`, `bedrooms`, `beds`, `bathrooms`, `review_scores_*`, and `reviews_per_month`: replace missing values with `0`.
- Date fields such as `first_review`, `last_review`, and `host_since`: replace missing values with `1900-01-01`.
- Boolean-like host fields such as `host_has_profile_pic` and `host_identity_verified`: replace missing values with `f`.
- `host_verifications`: replace missing values with `[]`.

Latest null replacement audit:

- Initial rows: `103,708`
- Final rows: `103,708`
- Rows removed by `Remove empty`: `0`
- Columns touched by null actions: `43`
- Total null cells before replacement: `774,641`
- Total null cells after replacement: `0`

## Standardized Pipeline Outputs

The listing script writes the standardized outputs directly:

```text
data/processed/listing/<city>/listing_<city>_cleaned.csv
data/processed/listing_all_cleaned.csv
```

`listing_all_cleaned.csv` is the listing input used by the calendar occupation step and by the final `master_data.csv` join.

## Dtype Rules

The script uses embedded rules instead of an EDA-generated dtype CSV:

- Known text and identifier columns are coerced to string.
- Known date columns and columns ending in `_date` are parsed as dates.
- Known boolean columns are mapped from values such as `t`, `f`, `true`, `false`, `1`, and `0`.
- Known integer count columns, including `accommodates`, are coerced to nullable integer (`Int64`).
- Known rates, scores, prices, and average-night columns are coerced to numeric floats.
- Any remaining shared columns default to cleaned strings.

## Relationship to EDA

`notebooks/EDA_listing_csv.ipynb` should only inspect and summarize raw listing data. It should not:

- execute cleaning scripts,
- write pipeline input files,
- trigger listing, review, or calendar processing.

The notebook may display suggested dtype patterns and null profiles as EDA findings, but production cleaning behavior belongs in the scripts under `scripts/cleaning/`.
