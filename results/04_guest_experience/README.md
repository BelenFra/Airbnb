# `results/04_guest_experience/` — Guest Experience Questions

Outputs that answer the **Guest Experience Questions** in the TP brief and
the text-analytics method (TP Section 4). The substrate is the cleaned
`comments_clean` column produced by the reviews pipeline.

- What do guests complain about most? Does it differ by city or property type?
- Which guest-experience factors (cleanliness, check-in, communication,
  location) matter most for 5-star reviews?
- Which operational investments (self-check-in, professional cleaning, …)
  does the review data say would pay off?
- What do guests praise in the top-performing listings that the client
  should replicate?

## Suggested artefacts

| File | Produced by | Describes |
| --- | --- | --- |
| `sentiment_by_city.csv` | sentiment script | Per-city polarity / subjectivity / 5-star share, plus monthly trend. |
| `sentiment_by_segment.csv` | sentiment script | Same, broken down by cluster / property type. |
| `topic_keywords.csv` | topic-model script | Topic id, top-N keywords (TF-IDF / LDA / NMF), interpretation label. |
| `complaints_top10.csv` | TBD | Top recurring complaint topics + example excerpts (per city or overall). |
| `praises_top10.csv` | TBD | Top recurring praise topics + example excerpts. |
| `operational_payoff.csv` | TBD | Suggested operational features → estimated price / occupancy uplift, citing the supervised models in `03_pricing_models/`. |

## Conventions

- All analyses use `comments_clean` (HTML-free, lower-cased) from
  `data/processed/review/<city>/reviews_<city>_cleaned.csv`.
- For multilingual analyses, document the language detection / translation
  step in the script (`langdetect`, `googletrans`, etc.) — the cleaning step
  intentionally does **not** filter by language (see
  `scripts/cleaning/reviews/review_cleaning_decisions.md`, Section 5).
- Topic-model labels are interpreted manually and added to a `topic_label`
  column; do not ship raw topic ids to the memo.
