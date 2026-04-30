# Q1 — What do guests complain about? City and property type

## Answer (headline)

- **Relative complaint-friction in text:** We flag review comments that contain **practical complaint cues** (noise, smell, cleanliness/break/fix issues, delays, disappointment, etc. — regex over `comments_clean`).
- **By city**, the highest share of reviews with at least one such cue is **Hawaii** (20.1% of in-scope reviews).
- **By property type**, among types with **≥500 in-scope reviews**, the highest complaint-cue share is **Room in hotel** (34.0%). (See full table for rare types — small volumes can hit 100% in error.)

## Method

- One pass over `data\processed\reviews_all_cleaned.csv` in chunks (200,000 rows).
- Inner join to `master_data` for `City` and `property_type`.
- **Outcome:** `share_complaint_cue` = reviews with ≥1 regex hit / all joined reviews.

## Evidence

- `q1_complaint_cue_rate_by_city.csv`
- `q1_complaint_cue_rate_by_property_type.csv`


**City-discriminating vocabulary** (TF-IDF on city mega-documents): see `../text_features/city_corpus_top_terms.csv` and ranks in that file per city.

### By city

| City | reviews_in_scope | reviews_complaint_cue | share_complaint_cue |
| --- | --- | --- | --- |
| Hawaii | 1324881 | 265916 | 0.200709 |
| New York | 721102 | 127232 | 0.176441 |
| San Francisco | 348017 | 55584 | 0.159716 |
| Nashville | 619421 | 96395 | 0.155621 |
| Los Angeles | 1427751 | 216147 | 0.15139 |


### By property type (top 15 by rate)

| property_type | reviews_in_scope | reviews_complaint_cue | share_complaint_cue |
| --- | --- | --- | --- |
| Private room in dome | 1 | 1 | 1.0 |
| Cycladic home | 4 | 2 | 0.5 |
| Private room in kezhan | 8 | 4 | 0.5 |
| Private room in treehouse | 45 | 20 | 0.444444 |
| Room in hotel | 60393 | 20545 | 0.340188 |
| Room in boutique hotel | 39089 | 13202 | 0.337742 |
| Room in serviced apartment | 183 | 59 | 0.322404 |
| Entire bed and breakfast | 46 | 13 | 0.282609 |
| Private room in houseboat | 211 | 57 | 0.270142 |
| Island | 1270 | 315 | 0.248031 |
| Hut | 625 | 153 | 0.2448 |
| Tent | 558 | 136 | 0.243728 |
| Room in aparthotel | 19736 | 4734 | 0.239866 |
| Room in resort | 117 | 28 | 0.239316 |
| Private room in hostel | 4372 | 991 | 0.22667 |


## Business interpretation

Higher **share_complaint_cue** means guests in that slice more often use **problem-oriented language** in free text. Combine with structured sub-scores and ops checks before treating as “worse operations.” **Property-type** differences often reflect **product heterogeneity** (e.g., whole-home vs shared) rather than management quality alone.
