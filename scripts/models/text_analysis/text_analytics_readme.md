# Text analytics & text mining (MBA 706)

This document defines the **Unstructured Data and Text Mining** framework used in the Airbnb project: how we turn guest review text into structured features for listing-level and city-level analysis, and how those pieces connect to the Investment Memo.

**Code & methodology location:** This folder (`scripts/models/text_analysis/`) contains this README, preprocessing/core modules, and **`run_hierarchical_text_mining.py`**.

## 1. Objects: Document and Corpus

### Document (listing level)

A **document** \(d\) is one logical text unit for **one listing** (`listing_id`). We form it by **concatenating** all cleaned review bodies for that listing (from `comments_clean`), after project-specific preprocessing (see §3). One row in the listing-level dataset = one document + metadata (`listing_id`, `City`, review count, character length).

**Rationale:** Topics such as noise, cleanliness, or amenities often appear across multiple stays; aggregating at the listing level yields a stable profile comparable across listings within the same market.

### Corpus (city / market level)

A **corpus** for a market is the **collection of all documents** whose listings belong to that **city** (e.g. New York, Los Angeles, San Francisco, Nashville, Hawaii). At **Analysis Level 2**, we also build a **single pseudo-document per city** by concatenating all review text in that city, to compare **market-wide vocabulary and sentiment** across the five markets.

## 2. Bag of Words (BoW)

The **bag-of-words** representation ignores word order. Each document is mapped to a vector of **term frequencies** over a vocabulary \(V\):

- **Term frequency** \(\mathrm{TF}(t, d)\): count (or a variant thereof) of term \(t\) in document \(d\), after tokenization and preprocessing.
- The vector for \(d\) has dimension \(|V|\); it is **sparse** in practice (most terms are zero).

We use scikit-learn’s `CountVectorizer` logic conceptually for counts; in production we use **TF-IDF** weighting (§4) on the same tokenization path.

## 3. Preprocessing (governance)

Raw reviews are first cleaned in **`scripts/cleaning/reviews/run_full_review_cleaning.py`** (HTML stripped, lowercased, whitespace normalized). The text analytics pipeline adds:

| Step | Purpose |
|------|---------|
| **Normalization** | Lowercase (redundant but idempotent), remove non-alphanumeric except spaces (drops punctuation). |
| **Stopwords** | Remove high-frequency low-information English words via `TfidfVectorizer(stop_words="english")`. |
| **Stemming** | Reduce inflected/derived forms (`cleaning`, `clean`) to a common stem with **Porter stemmer** (`nltk.stem.PorterStemmer`). |

This aligns with standard “Unstructured Data and Text Mining” syllabi: normalize → tokenize → optionally stem → vectorize.

## 4. TF–IDF

**Term frequency–inverse document frequency** downweights terms that appear in many documents and upweights terms that are **characteristic** of a document:

\[
\mathrm{TFIDF}(t,d) = \mathrm{TF}(t,d) \times \mathrm{IDF}(t)
\]

With the usual sklearn definition, \(\mathrm{IDF}(t)\) reflects how rare \(t\) is across the corpus (with smoothing). We use `TfidfVectorizer` with document frequency floors/ceilings (`min_df`, `max_df`) to drop ultra-rare noise and boilerplate, and optionally **sublinear TF** ( \(1 + \log(\mathrm{TF})\) ) to damp very frequent terms within a document.

## 5. Analysis levels (execution)

### Level 1 — Listing vs city baseline

1. Build one document per `listing_id`.
2. Fit **TF-IDF** on the **set of all listing documents** (shared vocabulary).
3. For each city, compute the **mean** (and dispersion) of each term’s TF-IDF weight across listings in that city.
4. For each listing, flag terms whose TF-IDF **exceeds** the city baseline (e.g. z-score or ratio) to surface **listing-specific themes** (e.g. noise, cleanliness) relative to peers in the same market.

### Level 2 — City / market comparison

1. Build **one concatenated document per city** (corpus summary).
2. Fit TF-IDF on the **five city-level documents** to obtain **market-discriminating** terms.
3. Compute **average sentiment** (TextBlob polarity) per review, aggregated by city, for cross-market sentiment comparison in the Investment Memo.

## 6. Outputs and code map

| Output | Location | Role |
|--------|----------|------|
| Listing-level sparse TF-IDF matrix | `results/04_guest_experience/text_features/listing_tfidf_matrix.npz` | Document–term matrix (CSR). |
| Row order ↔ `listing_id` | `results/04_guest_experience/text_features/listing_tfidf_row_index.csv` | Aligns matrix rows to listings. (Local output; gitignored with the listing matrix.) |
| Vocabulary | `results/04_guest_experience/text_features/listing_tfidf_vocabulary.json` | Feature names (stemmed tokens). |
| Listing metadata | `results/04_guest_experience/text_features/listing_documents_meta.csv` | `listing_id`, `City`, `n_reviews`, etc. (Local output; gitignored.) |
| Listing–term deviations | `results/04_guest_experience/text_features/listing_city_deviation_terms.csv` | Terms above city baseline (long format). |
| City corpus TF-IDF | `results/04_guest_experience/text_features/city_corpus_tfidf_matrix.npz` | 5×|V| sparse matrix. |
| City corpus index | `results/04_guest_experience/text_features/city_corpus_tfidf_rows.csv` | City label per row. |
| City vocabulary | `results/04_guest_experience/text_features/city_corpus_tfidf_vocabulary.json` | May match listing vocab if refit. |
| City sentiment summary | `results/04_guest_experience/text_features/city_sentiment_summary.csv` | Mean polarity, counts by `City`. |
| City top terms | `results/04_guest_experience/text_features/city_corpus_top_terms.csv` | Top weighted terms per city. |

**Entry point:** `scripts/models/text_analysis/run_hierarchical_text_mining.py`

**Inputs (resolved in code):**

- Reviews: `data/processed/reviews_all_cleaned.csv` or alias `data/processed/all_reviews_cleaned.csv`
- Listing → city: `data/processed/master_data.csv` (`id`, `City`)

## 7. Reproducibility

- Random seeds where applicable: **`RANDOM_STATE = 42`** (project standard).
- Large-scale aggregation uses **chunked** reads of the reviews file to limit peak memory.

## 8. Agent / toolkit note

Feature construction uses **scikit-learn** `TfidfVectorizer` for hierarchical listing- vs city-level documents; this goes beyond the stock `create_tfidf_features()` helper in `mba706_toolkit.py` (which expects one row per record in an in-memory store). Data loading should still use **`load_data()`** / **`load_excel_data()`** when pulling project CSVs. See **`AGENTS.md`** (project root) for the dedicated Text Analytics rules.
