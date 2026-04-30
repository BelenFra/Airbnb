# Calendar Data Cleaning Decisions

> Scope: the five-city `calendar.csv` files for the MBA706 Term Project (Hawaii / Los Angeles / Nashville / New York / San Francisco).
> Last updated: 2026-04-30.

## 1. Naming and Hand-off Conventions (shared with Belu / Agostino)

| Field | Convention |
| --- | --- |
| `city` values | `hawaii`, `los_angeles`, `nashville`, `new_york`, `san_francisco` (snake_case) |
| `listing_id` | Keep the original Inside Airbnb `int64`; never rename |
| Date format | `YYYY-MM-DD` strings |
| Missing values | Use `NaN` everywhere; never use empty strings, `"NA"`, or `"None"` |
| File encoding | UTF-8 (BOM tolerated via `utf-8-sig` on read) |

**Why:** the listings / reviews / calendar deliverables must join unambiguously on `(listing_id, city)`.

## 2. Inputs and Outputs

Aligned with `scripts/cleaning/calendars/run_full_calendar_cleaning.py` (paths relative to project root).

### Inputs

- One raw file per city: `data/raw/calendars/calendar_<city_slug>.csv`  
  where `<city_slug>` ∈ `{hawaii, los_angeles, nashville, new_york, san_francisco}`.
- **Upstream dependency:** cleaned listings master `data/processed/listing_all_cleaned.csv` (needed for `listing_price` on the occupation table). Run listing cleaning before calendar occupation.

### Per-city outputs (`data/processed/calendar/<city_slug>/`)

| File | Description |
| --- | --- |
| `calendar_<city_slug>_cleaned.csv` | Row-level cleaned calendar (`listing_id`, `city`, `date`, `available`, prices, nights). **Not written** if `--occupation-only`. |
| `occupation_<city_slug>_cleaned.csv` | Listing-level roll-up (availability / occupancy proxy, joined listing price, revenue proxy). |

### Merged outputs (`data/processed/`)

| File | Description |
| --- | --- |
| `calendar_all_cleaned.csv` | Concatenation of all per-city row-level files (large; optional). **Skipped** with `--no-merged-rows` or `--occupation-only`. |
| `occupation_all_cleaned.csv` | Concatenation of all five `occupation_<slug>_cleaned.csv` files (**primary hand-off** for `master_data.csv` join in `scripts/cleaning/run_cleaning_pipeline.py`). |

### Audit / QC

| File | Description |
| --- | --- |
| `results/01_market_analysis/calendars/calendars_cleaning_audit.csv` | Per-city row counts, clipping counters, proxy KPIs (written every run). |

### Orchestration

- Prefer `python scripts/cleaning/run_cleaning_pipeline.py --calendar-write-row-files` so listing → reviews → calendar → join order is enforced (see `AGENTS.md`).

### Documentation

- `scripts/cleaning/calendars/calendar_cleaning_decisions.md` — this file (cleaning rules).
- `data/processed/calendar/README.md` — hand-off for which CSV to use / joins / warnings.
- `AGENTS.md` and root `README.md` — orchestrator order and processed-data layout tables.

## 3. Row-level Cleaning Rules (executed inside the streaming pass)

The following are applied in order on each `chunksize=200_000` chunk:

1. **Column projection**: keep only `listing_id, date, available, price, adjusted_price, minimum_nights, maximum_nights`.
2. **Deduplication**: hash all seven columns and globally drop duplicates, keeping the first occurrence.
3. **Required fields**: drop rows where any of `listing_id`, `date`, `available` is null.
4. **Date parsing**: `pd.to_datetime(errors="coerce")`; drop rows that fail; emit `YYYY-MM-DD` strings.
5. **`available` normalization**: map `t/true/1 → True`, `f/false/0 → False`; drop other values.
6. **Price cleaning**: strip non-numeric characters (`$`, `,`, whitespace) from `price` and `adjusted_price`, then cast to `float`. `NaN` is allowed (it is the Inside Airbnb default on unavailable days).
7. **Integer columns**: cast `minimum_nights`, `maximum_nights` to `Int64`.
8. **Outlier handling (clip + count, no row drops)**:
   - `price > 10000` → set to `NaN`, count.
   - `minimum_nights` clipped to `[1, 1125]`; `maximum_nights` clipped to `[1, 1125]` (Airbnb platform max).
   - **No quantile-based price clipping at the row level** — that distorts "looks cheap, gets removed". Downstream models can apply per-city quantile clipping when needed.
9. **Add `city` column** — snake_case slug (`hawaii`, `los_angeles`, …) for the city pass being streamed.

Output column order: `listing_id, city, date, available, price, adjusted_price, minimum_nights, maximum_nights`.

## 4. Listing-level Occupancy Rules

Within the same streaming pass, the following are accumulated per `listing_id`:

- `n_days` — number of rows for this listing in this city's calendar.
- `n_days_available` — count where `available == True`.
- `n_days_unavailable` — count where `available == False`.
- `first_date` / `last_date` — min / max date.
- `price_sum_when_available`, `price_count_when_available` — accumulated when price is non-null and `available == True`.
- `price_sum_when_unavailable`, `price_count_when_unavailable` — accumulated when price is non-null and `available == False`.
- `min_minimum_nights`, `max_maximum_nights`.

Derived metrics (computed once at the end):

- `availability_rate = n_days_available / n_days`.
- `unavailability_rate = n_days_unavailable / n_days`.
- `occupancy_rate_proxy = unavailability_rate`.
  - **Important**: `available=f` in Inside Airbnb does **not** strictly mean "booked" — it can also be a host-imposed block. We therefore use `unavailability_rate` as a **proxy** for occupancy, and label it accordingly throughout. If the team decides to switch to a review-based estimate later (the San Francisco model), the reviews team will provide `reviews_per_year` and we'll combine.
- `listing_price` — joined from `listings.csv` for the same city (Inside Airbnb removed nightly prices from recent calendar dumps; see Section 5).
- `est_annual_revenue_proxy = listing_price × occupancy_rate_proxy × 365`.
  - Falls back to `NaN` when `listing_price` is missing.

## 5. Things I Deliberately Did **Not** Do

- Quantile-based price clipping (do that at modeling time on a per-city basis with P1 / P99).
- Imputation of missing prices (don't fill with a global mean — recommend `room_type × neighborhood` median, owned by the listings team).
- Joining to the listings table beyond `id → listing_price` (the merged listing-level table only carries `listing_id` + `city` + the price scalar; full listings join belongs to Belu).
- Fusion with reviews-based occupancy (San Francisco model — collaboration with Agostino once reviews are clean).

## 6. Known Risks and Reminders

- **Volume**: LA 622 MB, NYC 471 MB, HI 442 MB. Always read with `chunksize`; never `pd.read_csv` the full file.
- **Right-skewed prices**: Hawaii / SF top-end prices dwarf Nashville. Any cross-city price comparison must be done per-city.
- **Occupancy proxy is biased high**: it includes host-blocked days. Always disclose this in the memo and any chart.
- **Calendar windows are not always 365 days**: newly listed / delisted units can have `n_days < 365`. Use `n_days` as the denominator, not a hard-coded 365.
- **All paths must be relative to `PROJECT_ROOT`**: never hard-code OneDrive absolute paths in scripts.
