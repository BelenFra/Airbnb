# Q3 — Operational investments suggested by listings + reviews

## Answer (headline)

We proxy “investments” with **listing amenity flags** parsed from the `amenities` text (e.g., **Self check-in**, **smart lock / lockbox**, **cleaning** mentions) plus **`instant_bookable`**. For each flag we compare **mean overall review score** and **share of listings with overall ≥ 4.9**.

> **Caution:** Amenities correlate with **market tier, host professionalism, and property type** — these are **associations**, not proof that adding an amenity **causes** higher ratings.

Top signals by mean rating (flag=True rows) — see CSV for full table:

| signal | flag | n_listings | mean_overall_rating | share_high_overall_ge_4_9 |
| --- | --- | --- | --- | --- |
| keypad_lockbox | True | 54457 | 4.2323 | 0.4291 |
| cleaning_fee_listed | True | 44188 | 4.1468 | 0.4784 |
| self_checkin_amenity | True | 64528 | 4.0096 | 0.4091 |
| host_greets | True | 7758 | 3.9445 | 0.4241 |
| carbon_alarm | True | 78385 | 3.6635 | 0.3889 |
| instant_bookable_flag | True | 38715 | 3.6513 | 0.3334 |


## Method

- String match / regex on `amenities` (case-insensitive).
- Group-wise means on `review_scores_rating`.

## Evidence

- `q3_operational_signal_assoc.csv`
- Figure (toolkit boxplot): `reports/figures/` (see latest guest-experience plot saved by toolkit naming).

## Business interpretation

Listings that advertise **lockbox / keypad / smart-lock** language and **cleaning**-related amenities show **higher average overall ratings** in this snapshot than those without — but hosts who bundle more amenities may differ on many other dimensions. **Instant Book** rows here have **lower** average ratings (often risk-taking hosts or different segments), so treat as descriptive only.
