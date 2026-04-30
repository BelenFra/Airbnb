# Calendar Dataset — Team Hand-off README

> Last updated: 2026-04-29 (paths re-aligned with the standardized cleaning pipeline).
> Related document: `scripts/cleaning/calendars/calendar_cleaning_decisions.md` (cleaning rules).
> Snapshot kept: `data/processed/calendar/calendar_cleaning_audit.csv` (last full run by Will, kept for reproducibility audits).

## 1. Which file should I use?

| Use case | File | Rows / size |
| --- | --- | --- |
| Listing-level investment comparison or modeling | `data/processed/occupation_all_cleaned.csv` | 132,677 rows / 16 MB |
| Single-city occupancy analysis | `data/processed/calendar/<city>/occupation_<city>_cleaned.csv` | see table below |
| Multi-city day-level time series (seasonality, weekly patterns) | `data/processed/calendar_all_cleaned.csv` | ~48.4M rows / 2.3 GB |
| Single-city day-level time series | `data/processed/calendar/<city>/calendar_<city>_cleaned.csv` | see table below |
| Cleaning audit / decision tracking | `results/01_market_analysis/calendars/calendars_cleaning_audit.csv` (live) and `data/processed/calendar/calendar_cleaning_audit.csv` (snapshot) | 5 rows |

> **Recommendation**: unless you specifically need seasonality, **default to `occupation_all_cleaned.csv`**. It collapses the 365-day calendar to one row per listing and already joins in `listing_price` from `listing_all_cleaned.csv`.

## 2. Five-city Snapshot (post-clean)

| City | listings | with price (%) | mean occupancy proxy | median listing price | median annual revenue proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| hawaii | 33,457 | 97.6% | 37.0% | $230 | $26,100 |
| los_angeles | 45,886 | 80.1% | 41.7% | $155 | $10,278 |
| nashville | 9,443 | 70.2% | 31.5% | $158 | $10,803 |
| new_york | 36,111 | 58.5% | 55.6% | $152 | $11,960 |
| san_francisco | 7,780 | 74.3% | 48.0% | $170 | $18,196 |
| **Total** | **132,677** | **77.6%** | — | — | — |

> Business intuition (discussion starters, not conclusions):
> - Hawaii has the highest prices (mean $434, median $230) and the highest annual revenue, despite an occupancy of only 37% → high price, low turnover.
> - NYC has the highest occupancy (55.6%) at a moderate price ($152), but 41% of NYC listings are missing prices (regulation / compliance redactions) → mind the data gaps.
> - SF has both high price and high occupancy on the smallest supply (7,780 listings) → tight supply with decent unit economics.
> - LA has the largest supply (45,886) but neither premium prices nor leading revenue → most competitive market.

## 3. Field Definitions (`occupation_<city_slug>_cleaned.csv`, listing-level)

| Column | Meaning | Notes |
| --- | --- | --- |
| `listing_id` | Inside Airbnb listing primary key | `int64`; join key with listings / reviews |
| `city` | City | snake_case: hawaii / los_angeles / nashville / new_york / san_francisco |
| `n_days` | Number of calendar days observed for this listing | Usually 365 |
| `first_date` / `last_date` | Calendar window start / end | `YYYY-MM-DD` strings |
| `n_days_available` / `n_days_unavailable` | Bookable / unbookable day counts | from `available == True / False` |
| `availability_rate` | `n_days_available / n_days` | |
| `unavailability_rate` | `n_days_unavailable / n_days` | |
| `occupancy_rate_proxy` | **Occupancy proxy** | Equal to `unavailability_rate`. **Not actual occupancy** — see Section 5. |
| `listing_price` | Listed nightly price joined from `listing_all_cleaned.csv` (USD/night) | `$` and `,` stripped; can be NaN, especially in NYC |
| `min_minimum_nights` | Minimum `minimum_nights` seen across the calendar | clipped to [1, 1125] |
| `max_maximum_nights` | Maximum `maximum_nights` seen across the calendar | clipped to [1, 1125] |
| `est_annual_revenue_proxy` | **Annual revenue proxy** | `listing_price × occupancy_rate_proxy × 365`; NaN when `listing_price` is missing |

## 4. Field Definitions (`calendar_<city_slug>_cleaned.csv`, row-level)

`listing_id, city, date, available, price, adjusted_price, minimum_nights, maximum_nights`

- `date`: `YYYY-MM-DD`.
- `available`: bool (True = bookable, False = unavailable).
- `price` / `adjusted_price`: **almost always NaN** — Inside Airbnb's recent calendar dumps no longer carry per-night prices. Use `listing_price` from the occupation table or `listing_all_cleaned.csv` instead.
- `minimum_nights` / `maximum_nights`: `Int64`, clipped to [1, 1125].

## 5. Important Warnings (please read)

1. **`occupancy_rate_proxy` is not the true booking rate.**
   In Inside Airbnb, `available=False` covers both "booked" and "host-blocked"; the two are indistinguishable. The metric **systematically overestimates** real bookings.
   - To get closer to true bookings, plug in reviews-based estimates (San Francisco model: review_rate=50%, avg_nights=3). That work belongs to the reviews lead (Agostino) + me.
   - Always label the metric as "proxy" in the memo and figures — never call it "occupancy" without that qualifier.

2. **`listing_price` is the listed price, not a transaction price.** It does not reflect seasonal or last-minute discounts.

3. **NYC has 41% of listings without a price** (short-term rental regulation). If your analysis is price-sensitive (e.g., cross-city comparisons), either drop those listings or impute via `room_type × neighborhood` median in the listings table — that imputation should be owned by the listings lead (Belu).

4. **The `price` column inside `calendar.csv` is empty.** Don't average it (we already learned the hard way).

5. **`n_days` is not always 365.** Newly listed or delisted units can have shorter windows. Use `n_days` as the denominator, never a hard-coded 365.

## 6. How to Join

```python
import pandas as pd

occ = pd.read_csv('data/processed/occupation_all_cleaned.csv')
listings = pd.read_csv('data/processed/listing_all_cleaned.csv')  # Belu's deliverable
listings = listings.rename(columns={'id': 'listing_id', 'City': 'city_label'})
df = listings.merge(occ, on='listing_id', how='left')
```

> Conventions:
> - All teams keep `listing_id` as `int64` and use the column name `listing_id` (the listings table must rename `id` → `listing_id`).
> - All teams use the snake_case `city` values listed above.
> - Use a left join: keep all listings, calendar metrics become NaN where there is no calendar match.

## 7. Known Risks and Next Steps

- [ ] Sanity check with Belu: after listings cleaning, the `listing_id` join hit-rate against the calendar table should be ≥ 95%.
- [ ] Sync with Agostino: keep `city` consistent across reviews; later evaluate review-based occupancy.
- [ ] Price-imputation strategy: recommend the listings team impute by `room_type × neighborhood` median.
- [ ] Re-run: the script is idempotent — delete `data/processed/calendar/` and run `python scripts/cleaning/calendars/run_full_calendar_cleaning.py` (~22 minutes).

## 8. Reproduction Commands

```bash
python scripts/cleaning/calendars/run_full_calendar_cleaning.py
# Run only specific cities:
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --cities nashville san_francisco
# Skip the 2.3 GB merged row-level file (recommended when modeling, saves disk):
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --no-merged-rows
# Only listing-level occupation outputs (no row-level CSVs at all):
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --occupation-only
```

Inputs:
- Raw calendar files: `data/raw/calendars/calendar_<snake_city>.csv` (Inside Airbnb dump).
- Cleaned listings master (for prices): `data/processed/listing_all_cleaned.csv` (produced by `scripts/cleaning/listing/run_full_listing_cleaning.py`).

Outputs:
- Per-city: `data/processed/calendar/<city>/{calendar_<city>_cleaned.csv, occupation_<city>_cleaned.csv}`.
- Merged: `data/processed/calendar_all_cleaned.csv` (row-level, optional) and `data/processed/occupation_all_cleaned.csv` (listing-level).
- Audit: `results/01_market_analysis/calendars/calendars_cleaning_audit.csv` (live, regenerated each run).

Notes:
- All CSV outputs are written with `csv.QUOTE_ALL` (every field quoted, `\\` escape) so multi-line text fields cannot break row alignment.
- The legacy `data/Term Project/<City>/{calendar.csv, listings.csv}` layout is **no longer used**; the script now expects the `data/raw/calendars/calendar_<snake>.csv` layout shipped in this repo.
