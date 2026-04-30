# Reviews Data Cleaning Decisions

> Scope: the five-city `reviews.csv` files for the MBA706 Term Project (Hawaii / Los Angeles / Nashville / New York / San Francisco).
> Last updated: 2026-04-29.
> Companion memo: `scripts/cleaning/calendars/calendar_cleaning_decisions.md` (calendar pipeline) and `scripts/cleaning/listing/listing_cleaning_decisions.md` (listing pipeline).

## 1. Naming and Hand-off Conventions (shared with Belu / Will)

| Field | Convention |
| --- | --- |
| `city` slug used in filenames | `hawaii`, `los_angeles`, `nashville`, `new_york`, `san_francisco` (snake_case) |
| `listing_id` | Keep the original Inside Airbnb `int64`; never rename |
| Date format | `YYYY-MM-DD` strings |
| Missing values | Use `NaN` everywhere; never `""`, `"NA"`, `"None"` |
| File encoding | UTF-8 (BOM tolerated via `utf-8-sig` on read) |
| Output CSV quoting | `csv.QUOTE_ALL`, `quotechar='"'`, `escapechar='\\'` (see Section 6) |

**Why:** the listings / reviews / calendar deliverables must join unambiguously on `(listing_id, city)`. Reviews additionally need bullet-proof CSV escaping because comments can contain newlines, commas, and quotes.

## 2. Inputs and Outputs

- Inputs: `data/raw/reviews/reviews_<city>.csv` (five raw files).
- Outputs: `data/processed/review/`
  - `<city>/reviews_<city>_cleaned.csv` × 5 — per-city, row-level cleaned reviews with two added columns (`comments_clean`, `comments_clean_length`).
  - `data/processed/reviews_all_cleaned.csv` — five cities concatenated, same schema (cross-city deliverable).
  - `results/01_market_analysis/reviews/reviews_cleaning_audit.csv` — per-city cleaning audit (rows in/out, drop reasons, etc.).
- Documentation:
  - `scripts/cleaning/reviews/review_cleaning_decisions.md` — this file (technical, why-each-rule).
  - `data/processed/review/README.md` — dataset hand-off doc for the team.
  - `data/raw/reviews/_eda/raw_data_memo_reviews.md` — business-facing EDA on the raw input.
  - `data/processed/review/_eda/processed_data_memo_reviews.md` — business-facing EDA on the cleaned output (post-pipeline state + raw↔cleaned reconciliation).

## 3. Row-level Cleaning Rules (executed inside the streaming pass)

Applied in order on each `chunksize=200_000` chunk:

1. **Column projection**: keep only `listing_id, id, date, reviewer_id, reviewer_name, comments` (the 6 raw columns from Inside Airbnb).
2. **Trim and standardize missing tokens**: every column is cast to `string`, stripped, and `""`, `"nan"`, `"None"` are replaced by `pd.NA` (`clean_missing_text`).
3. **Deduplication**: hash all six columns and globally drop duplicates inside one city's file (keep first occurrence). This catches re-scraped or accidentally-duplicated records.
4. **Required fields**: drop rows where ANY of the six columns is null after step 2. Per the TP business goal (text analytics, demand proxy), a review without a `comments` body is useless.
5. **Comment text cleaning** (only `comments` is touched; the original is **not** kept):
   1. `html.unescape` to convert `&amp;` → `&`, `&lt;` → `<`, etc.
   2. Strip HTML tags via `re.sub(r"<[^>]+>", " ", text)` — Airbnb sends `<br/>` for line breaks; we replace with whitespace, not delete, so words don't merge.
   3. Collapse all whitespace runs to single spaces (`\s+ → " "`).
   4. Lowercase. This is required for downstream sentiment / topic / n-gram models, where casing introduces unhelpful vocabulary explosion.
6. **Length filter**: drop rows where `len(comments_clean) < 30`. Threshold is configurable via `--min-length`. **Rationale below in Section 5.**
7. **Add two columns**: `comments_clean` (the cleaned text) and `comments_clean_length` (its character length). The original `comments` column is **kept** alongside, so any reviewer can recover the raw text if needed.
8. **Write per-city output** with `csv.QUOTE_ALL` (Section 6 explains why).

Output column order: `listing_id, id, date, reviewer_id, reviewer_name, comments, comments_clean, comments_clean_length`.

After all five cities are processed, the script also concatenates the per-city outputs into `data/processed/reviews_all_cleaned.csv` with the same `csv.QUOTE_ALL` settings.

## 4. Audit Counters

Per city (recorded in `results/01_market_analysis/reviews/reviews_cleaning_audit.csv`):

- `rows_in`, `rows_out`, `rows_removed_total`, `percent_removed`.
- `duplicate_rows_removed` — caught in step 3.
- `missing_rows_removed` — caught in step 4.
- `rows_with_html_tags` — diagnostic (counted on raw input).
- `rows_changed_by_text_cleaning` — non-trivial cleaning happened (HTML / whitespace / case).
- `blank_after_cleaning` — became empty after step 5 (HTML-only, whitespace-only).
- `short_comments_removed` — survived blank check but failed length threshold.
- `min_comment_length`, `avg_kept_comment_length`.

## 5. Things I Deliberately Did **Not** Do

- **Did not drop very long comments.** Some Airbnb reviews exceed 1,000 characters; these are usually rich, opinionated, and useful for topic modeling. We do not treat length-outliers as data errors.
- **Did not translate non-English comments.** ~25–28% of comments contain non-ASCII characters (more in Hawaii / NYC). Translation is a downstream concern (multilingual sentiment models exist and we will choose at modeling time). Keeping them lets us measure international-traveler share by city.
- **Did not normalize emojis or contractions.** Lower-case + whitespace normalization is the only text transformation. Anything more aggressive (stemming, lemmatization, stopword removal) is owned by the text-analytics step where it can be tuned per technique.
- **Did not impute missing review IDs / dates.** Anything missing in step 4 is dropped — the cost of fabricating an `id` or a `date` is greater than the cost of losing ~0.02% of rows.
- **Did not filter on language.** "English share" is reported in the EDA memo (a heuristic stop-word count) but no row is dropped for being non-English; that's a modeling-time decision.
- **Did not use Inside Airbnb's `reviews_id` to compute occupancy.** The "San Francisco model" (review-rate ≈ 50%, avg-nights ≈ 3 → bookings ≈ reviews × 2; nights ≈ bookings × avg-nights) is implemented in the **calendar pipeline / downstream notebook**, not here. This script is the data-quality gate; the demand-proxy math lives where the calendar lives.

## 6. Why `csv.QUOTE_ALL` Matters (the `<br/>`/newline fix)

**Initial bug observed (2026-04-29):** the inventory script flagged ~21k `bad_listing_id` rows and ~8.5k unparseable `bad_date` rows in the cleaned output, even though the per-row cleaning rules were correct.

**Root cause:** Inside Airbnb review comments contain literal newlines (in addition to `<br/>` tags). The default `pandas.to_csv(quoting=csv.QUOTE_MINIMAL)` only quotes a field when it sees `,` or `"`. A bare `\n` inside an unquoted comment was silently treated by readers (and by `pandas.read_csv` itself in some chunks) as an end-of-row, splitting one logical row into two physical rows. The split ones had a numeric ID landing in the `listing_id` column for the first half and the rest of the comment landing in `listing_id` for the second half — hence "bad_listing_id".

**Fix applied here:** every `to_csv(...)` call uses

```python
quoting=csv.QUOTE_ALL,
quotechar='"',
escapechar='\\',
```

This wraps every field in double quotes (so embedded `\n`, `,`, `"` are unambiguous) and escapes any literal `"` inside the field with `\\"`. After the fix, the same inventory script reports **zero** `bad_listing_id` and `bad_date` rows for all five cities (see `data/processed/review/_eda/processed_data_memo_reviews.md`, Residual issues section).

The same `QUOTE_ALL` policy was retroactively applied to the listing and calendar cleaning pipelines for consistency, even though they are less likely to encounter multi-line text.

## 7. Connection to the Term Project Business Question

This pipeline serves three downstream uses, all from the TP brief ("Where Should I Invest in Airbnb?"):

1. **Demand proxy** for the revenue equation `Price × Occupancy × 365`. The cleaned reviews give us `reviews_per_listing_per_year`, which the calendar lead uses to cross-check the `unavailability_rate` proxy and (optionally) to swap to the San Francisco model where `available=f` is too biased.
2. **Text analytics** (required method): sentiment + topic modeling on `comments_clean`. The lower-cased, HTML-stripped column is the input contract for that work.
3. **Guest-experience questions** (TP Section 2): "what do guests complain about / praise". The cleaned text is the substrate; the EDA memos document scale, languages, and time coverage so the analyst knows the limits of any conclusion drawn.

## 8. Known Risks and Reminders

- **File volume**: Hawaii 500 MB, LA 506 MB, NYC 310 MB. Always stream with `chunksize`; never `pd.read_csv` the full file. The script holds at most one chunk + a `set` of seen row hashes in memory (~250 MB peak observed).
- **Hash-based dedup is per-city.** Cross-city ID collisions don't exist in practice (Inside Airbnb IDs are global), but the dedup step intentionally never compares across cities; the merge file is a simple `concat` of per-city deduped outputs.
- **`QUOTE_ALL` ~doubles file size on disk.** The largest cleaned file is ~900 MB. This is the price of correctness; it does not affect downstream readers (`pandas.read_csv` handles `QUOTE_ALL` transparently).
- **Right-skewed comment lengths.** Mean / median / p95 differ by ~3-4× per city. Use median or quantile metrics, not mean, when reporting "typical comment length".
- **Cross-city comparisons assume same snapshot.** All five raw files were downloaded from Inside Airbnb on 2025-09-XX. If we re-pull at a later date, the snapshot must be redone for **all** five cities together; mixing snapshots biases the year-over-year comparisons.
- **Paths are relative to `PROJECT_ROOT`.** Never hard-code OneDrive / Google Drive absolute paths in scripts.

## 9. Change log vs the original commit (`208bb45`)

The very first version of this pipeline was committed by Agostino as `208bb45` ("Add review cleaning pipeline structure"). Since then the script was extended during the pipeline standardisation and during the `bad_listing_id` post-mortem. For audit / TP defence, the differences are:

| # | Change | Type | Why |
| --- | --- | --- | --- |
| 1 | `clean_missing_text(series)` applied to all six columns inside the chunk loop (Section 3.2) before dedup and the missing-value filter | **Logic** | Without this, cells holding the literal string `""`, `"nan"` or `"None"` survived `notna().all()` and re-introduced empty reviews into `comments_clean`. Now they are forced to `pd.NA` and dropped by Section 3.4. This is the **only** behavioural change vs `208bb45`. |
| 2 | `to_csv(..., quoting=csv.QUOTE_ALL, quotechar='"', escapechar='\\', encoding='utf-8-sig')` | IO | Section 6 — fixes the `bad_listing_id`/`bad_date` artefact caused by un-escaped newlines. |
| 3 | Bootstrap block (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `MPLBACKEND=Agg`, `sys.path.insert(0, PROJECT_ROOT)`) | Reproducibility | Required by `AGENTS.md` for cross-platform runs. |
| 4 | Explicit `CITY_LABEL_BY_SNAKE` map + `WARN: unrecognized city snake` skip | Naming | The original `csv_file.stem.replace("reviews_", "")` produced `losangeles` (no underscore). The map-based discovery enforces project-wide snake_case (`los_angeles`) and drops unknown cities loudly instead of silently. |
| 5 | Output layout `data/processed/review/<city>/reviews_<city>_cleaned.csv` (subfolder + prefix `reviews_`) | Layout | Mirrors the layout used by listings (`data/processed/listing/<city>/listing_<city>_cleaned.csv`) and calendars (`data/processed/calendar/<city>/...`) so the orchestrator (`scripts/cleaning/run_cleaning_pipeline.py`) can address all three pipelines uniformly. |
| 6 | `merge_review_outputs(audit_rows)` → `data/processed/reviews_all_cleaned.csv` | Layout | Cross-city deliverable consumed by EDA / models / final memo. |
| 7 | Audit CSV also written with `QUOTE_ALL` + `utf-8-sig` | IO | Consistency with the row-level files. |
| 8 | Constants `RANDOM_STATE = 42`, `MISSING_TEXT_VALUES = {...}`, `REVIEWS_ALL_FILE` | Project rule | `AGENTS.md` requires `RANDOM_STATE = 42`; the rest are just to avoid magic strings. |

Everything else (column projection, dedup hash, HTML strip, length filter, audit counters) is identical to `208bb45`.
