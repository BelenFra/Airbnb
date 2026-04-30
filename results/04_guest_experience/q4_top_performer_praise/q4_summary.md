# Q4 — What do guests praise in top-performing listings?

## Answer (headline)

We define **top performers** as listings in the **top quartile** of `review_scores_rating` (4.97+). Using **listing–city TF‑IDF deviation terms** (words that **over-index** vs same-city peers), we compare which stems appear more often among top-quartile listings vs others.

**Frequently elevated terms among top listings (examples):** world, approach, goodi, recommend, thi, would, again, bay, friendli, experi, come, back, time, person, sister

> Deviation terms capture **distinctive language**, not pure “praise” — interpret with care. Positive hospitality language (**great**, **recommend**, **comfort**) often appears.

## Method

- File: `results\04_guest_experience\text_features\listing_city_deviation_terms.csv`
- Merge listing tiers from `master_data`.
- **Lift** ≈ (count in top + 1) / (count in other + 1) at the listing–term level.

## Evidence

- `q4_term_lift_top_vs_other.csv`

## Business interpretation

Themes that **separate** top guest perception from local peers are candidates for **standard playbooks**: **communication**, **cleanliness signals**, **location/description accuracy**, **amenities called out in reviews**. Validate each term qualitatively before rolling out “copy‑paste” host messaging.
