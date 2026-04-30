# Text features (`results/04_guest_experience/text_features/`)

Artifacts produced by **`scripts/models/text_analysis/run_hierarchical_text_mining.py`** (see **`scripts/models/text_analysis/text_analytics_readme.md`**).

| File | Description |
|------|-------------|
| `listing_tfidf_matrix.npz` | Sparse CSR: one row per listing, TF–IDF weights |
| `listing_tfidf_vocabulary.json` | Term names (stemmed), column order |
| `listing_tfidf_row_index.csv` | Maps matrix row index → `listing_id` |
| `listing_documents_meta.csv` | `listing_id`, `City`, lengths, review counts |
| `listing_city_deviation_terms.csv` | Long: terms above city-mean TF–IDF (z-scores) |
| `city_corpus_tfidf_matrix.npz` | Sparse CSR: one row per city corpus |
| `city_corpus_tfidf_vocabulary.json` | City-level vocabulary |
| `city_corpus_tfidf_rows.csv` | Row index → `City` |
| `city_corpus_top_terms.csv` | Top TF–IDF terms per market |
| `city_sentiment_summary.csv` | Mean TextBlob polarity by `City` |

Large binary/CSV outputs may be git-ignored; this README is tracked.

**Inputs:** `data/processed/reviews_all_cleaned.csv` (or `all_reviews_cleaned.csv`) + `data/processed/master_data.csv`.
