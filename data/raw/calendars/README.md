This folder is reserved for the raw Airbnb calendar datasets.

Place the uploaded calendar files here.

Naming pattern (snake_case, matches the rest of the project):
- `calendar_hawaii.csv`
- `calendar_los_angeles.csv`
- `calendar_nashville.csv`
- `calendar_new_york.csv`
- `calendar_san_francisco.csv`

These raw files are intentionally ignored by Git because they are large.

The cleaning pipeline that consumes them is `scripts/cleaning/calendars/run_full_calendar_cleaning.py`.
