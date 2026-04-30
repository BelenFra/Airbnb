# Q4 — What do guests praise in top-performing listings?

## Reproducibility

Q4 reads **`results/04_guest_experience/text_features/listing_city_deviation_terms.csv`**, which is produced by the hierarchical text-mining step. That file is **gitignored** (large; same regeneration pass as `listing_tfidf_matrix.npz`). **After a fresh clone** it will not exist.

- **To only read results:** use this `q4_summary.md` and `q4_term_lift_top_vs_other.csv` as committed artefacts.
- **To rerun Q4 locally:** (1) `python scripts/models/text_analysis/run_hierarchical_text_mining.py --skip-sentiment` — or omit `--skip-sentiment` if you need sentiment outputs; (2) `python scripts/04_guest_experience/run_guest_experience_questions.py`.

Running step (2) **without** the deviation CSV overwrites this summary with a short **Inputs not found** stub until step (1) has been completed.

## Answer (headline)

We define **top performers** as listings in the **top quartile** of `review_scores_rating` (4.97+). Using **listing–city TF‑IDF deviation terms** (words that **over-index** vs same-city peers), we compare which stems appear more often among top-quartile listings vs others.

**Frequently elevated terms among top listings (examples):** host, nice, clean, again, respons, recommend, would, we, amaz, love, help, everyth, thank, beauti, definit

> Deviation terms capture **distinctive language**, not pure “praise” — interpret with care. Positive hospitality language (**great**, **recommend**, **comfort**) often appears.

## Method

- File: `results\04_guest_experience\text_features\listing_city_deviation_terms.csv`
- Merge listing tiers from `master_data`.
- **Lift** ≈ (count in top + 1) / (count in other + 1) at the listing–term level.

## Evidence

- `q4_term_lift_top_vs_other.csv`

## Business interpretation

Themes that **separate** top guest perception from local peers are candidates for **standard playbooks**: **communication**, **cleanliness signals**, **location/description accuracy**, **amenities called out in reviews**. Validate each term qualitatively before rolling out “copy‑paste” host messaging.
