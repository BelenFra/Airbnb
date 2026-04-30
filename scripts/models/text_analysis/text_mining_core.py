"""
Core logic: aggregate reviews → listing documents, fit TF-IDF, city baselines,
city-level corpus matrix, and sentiment by city.

Uses scikit-learn TfidfVectorizer for hierarchical document matrices where the
toolkit's create_tfidf_features() is scoped to flat in-memory frames. master_data
is loaded with mba706_toolkit.load_data; reviews use chunked pandas I/O.
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from textblob import TextBlob

import mba706_toolkit as mba
from mba706_toolkit import load_data

from text_preprocessing import build_stem_analyzer

RANDOM_STATE = 42


def normalize_listing_id(series: pd.Series) -> pd.Series:
    """Align with cleaning pipeline: numeric IDs → canonical string."""
    return pd.to_numeric(series.astype("string").str.strip(), errors="coerce").astype("Int64").astype("string")


def resolve_reviews_path(project_root: Path) -> Path:
    """Canonical reviews_all_cleaned.csv; fallback all_reviews_cleaned.csv if needed."""
    p_canon = project_root / "data" / "processed" / "reviews_all_cleaned.csv"
    p_alias = project_root / "data" / "processed" / "all_reviews_cleaned.csv"
    if p_canon.exists():
        return p_canon
    if p_alias.exists():
        return p_alias
    raise FileNotFoundError(
        f"No reviews file found. Expected {p_canon} or {p_alias}."
    )


def load_master_listing_city(project_root: Path) -> dict[str, str]:
    """Load id → City from master_data via toolkit."""
    path = project_root / "data" / "processed" / "master_data.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing master data: {path}")
    result = load_data(str(path), dataset_name="master_text_mining")
    if result.get("status") != "success":
        raise RuntimeError(result)

    df = mba._data_store["master_text_mining"][["id", "City"]].copy()
    df["id"] = normalize_listing_id(df["id"])
    df = df.dropna(subset=["id", "City"])
    return dict(zip(df["id"].astype(str), df["City"].astype(str)))


def stream_aggregate_listing_documents(
    reviews_path: Path,
    chunksize: int,
    lid_to_city: dict[str, str],
) -> dict[str, str]:
    """
    One pass over reviews: concatenate comments_clean per listing_id.
    Retains only listings present in lid_to_city (master join).
    """
    buckets: dict[str, list[str]] = defaultdict(list)
    usecols = ["listing_id", "comments_clean"]
    peek = pd.read_csv(reviews_path, encoding="utf-8-sig", nrows=5)
    for c in usecols:
        if c not in peek.columns:
            raise ValueError(f"Reviews file missing column {c!r}. Found: {list(peek.columns)}")

    for chunk in pd.read_csv(
        reviews_path,
        usecols=usecols,
        chunksize=chunksize,
        encoding="utf-8-sig",
        dtype={"listing_id": "string"},
        low_memory=False,
    ):
        chunk["listing_id"] = normalize_listing_id(chunk["listing_id"])
        for lid, txt in zip(chunk["listing_id"], chunk["comments_clean"]):
            if lid is None or pd.isna(lid) or str(lid) not in lid_to_city:
                continue
            if pd.isna(txt):
                continue
            s = str(txt).strip()
            if not s:
                continue
            buckets[str(lid)].append(s)

    return {k: "\n".join(v) for k, v in buckets.items()}


def sentiment_by_city_stream(
    reviews_path: Path,
    chunksize: int,
    lid_to_city: dict[str, str],
) -> pd.DataFrame:
    """Second pass: TextBlob polarity averaged by city (review level)."""
    agg_sum: dict[str, float] = defaultdict(float)
    agg_cnt: dict[str, int] = defaultdict(int)
    usecols = ["listing_id", "comments_clean"]
    for chunk in pd.read_csv(
        reviews_path,
        usecols=usecols,
        chunksize=chunksize,
        encoding="utf-8-sig",
        dtype={"listing_id": "string"},
        low_memory=False,
    ):
        chunk["listing_id"] = normalize_listing_id(chunk["listing_id"])
        for lid, txt in zip(chunk["listing_id"], chunk["comments_clean"]):
            if lid is None or pd.isna(lid) or str(lid) not in lid_to_city:
                continue
            if pd.isna(txt):
                continue
            s = str(txt).strip()
            if not s:
                continue
            city = lid_to_city[str(lid)]
            pol = TextBlob(s).sentiment.polarity
            agg_sum[city] += float(pol)
            agg_cnt[city] += 1
    rows = []
    for city in sorted(agg_cnt.keys()):
        n = agg_cnt[city]
        rows.append(
            {
                "City": city,
                "n_reviews": n,
                "mean_sentiment_polarity": round(agg_sum[city] / n, 6) if n else np.nan,
            }
        )
    return pd.DataFrame(rows)


def fit_listing_tfidf(
    listing_docs: dict[str, str],
    lid_to_city: dict[str, str],
    max_features: int,
    min_df: int,
    max_df: float,
) -> tuple[TfidfVectorizer, list[str], list[str], sparse.csr_matrix]:
    """One TF-IDF row per listing; shared vocabulary across all markets."""
    analyzer = build_stem_analyzer()
    vectorizer = TfidfVectorizer(
        analyzer=analyzer,
        stop_words="english",
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
        sublinear_tf=True,
        dtype=np.float64,
    )
    listing_ids = sorted(listing_docs.keys())
    cities = [lid_to_city[lid] for lid in listing_ids]
    corpus = [listing_docs[lid] for lid in listing_ids]
    X = vectorizer.fit_transform(corpus)
    return vectorizer, listing_ids, cities, X


def sample_listings_if_requested(
    listing_docs: dict[str, str],
    max_listings: int | None,
) -> dict[str, str]:
    if max_listings is None or max_listings >= len(listing_docs):
        return listing_docs
    rng = random.Random(RANDOM_STATE)
    keys = list(listing_docs.keys())
    picked = rng.sample(keys, k=max_listings)
    return {k: listing_docs[k] for k in picked}


def listing_city_deviations(
    X: sparse.csr_matrix,
    listing_ids: list[str],
    cities: list[str],
    feature_names: np.ndarray,
    top_k: int = 15,
) -> pd.DataFrame:
    """
    Terms with highest positive z-score vs within-city mean TF-IDF across listings
    (surfaces listing-specific language vs local peers).
    """
    cities_unique = sorted(set(cities))
    city_masks = {c: np.array([cc == c for cc in cities]) for c in cities_unique}
    city_mu_sig: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for c in cities_unique:
        sub = X[city_masks[c]]
        if sub.shape[0] == 0:
            continue
        mu = np.asarray(sub.mean(axis=0)).ravel()
        mean_sq = np.asarray(sub.power(2).mean(axis=0)).ravel()
        var = np.maximum(mean_sq - mu**2, 1e-12)
        sig = np.sqrt(var)
        city_mu_sig[c] = (mu, sig)

    rows: list[dict[str, Any]] = []
    for i, lid in enumerate(listing_ids):
        c = cities[i]
        if c not in city_mu_sig:
            continue
        mu, sig = city_mu_sig[c]
        row = X.getrow(i)
        _, col = row.nonzero()
        data = row.data
        if len(col) == 0:
            continue
        z = (data - mu[col]) / (sig[col] + 1e-9)
        order = np.argsort(-z)[:top_k]
        for j in order:
            ti = int(col[j])
            rows.append(
                {
                    "listing_id": lid,
                    "City": c,
                    "term": str(feature_names[ti]),
                    "tfidf": float(data[j]),
                    "city_mean_tfidf": float(mu[ti]),
                    "z_vs_city_mean": float(z[j]),
                }
            )
    return pd.DataFrame(rows)


def city_corpus_from_listing_docs(
    listing_docs: dict[str, str],
    lid_to_city: dict[str, str],
) -> dict[str, str]:
    """Concatenate listing-level documents by City (market corpus)."""
    parts: dict[str, list[str]] = defaultdict(list)
    for lid, doc in listing_docs.items():
        city = lid_to_city.get(lid)
        if city:
            parts[city].append(doc)
    return {c: "\n".join(lst) for c, lst in parts.items()}


def fit_city_corpus_tfidf(
    city_texts: dict[str, str],
    max_features: int,
) -> tuple[TfidfVectorizer, sparse.csr_matrix, list[str]]:
    """One document per city; vocabulary sized for five markets."""
    analyzer = build_stem_analyzer()
    vec = TfidfVectorizer(
        analyzer=analyzer,
        stop_words="english",
        max_features=max_features,
        min_df=1,
        max_df=1.0,
        sublinear_tf=True,
        dtype=np.float64,
    )
    cities_sorted = sorted(city_texts.keys())
    X = vec.fit_transform([city_texts[c] for c in cities_sorted])
    return vec, X, cities_sorted


def city_top_terms_table(
    X: sparse.csr_matrix,
    cities_sorted: list[str],
    vocab: np.ndarray,
    top_n: int = 30,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, city in enumerate(cities_sorted):
        row = X.getrow(i)
        idx = row.indices
        data = row.data
        if len(data) == 0:
            continue
        top = np.argsort(-data)[:top_n]
        for rank, j in enumerate(top, start=1):
            ti = int(idx[j])
            rows.append(
                {
                    "City": city,
                    "rank": rank,
                    "term": str(vocab[ti]),
                    "tfidf": float(data[j]),
                }
            )
    return pd.DataFrame(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def run_pipeline(
    project_root: Path,
    out_dir: Path,
    chunksize: int = 200_000,
    max_features_listing: int = 8000,
    min_df_listing: int = 10,
    max_df_listing: float = 0.85,
    max_features_city: int = 4000,
    max_listings: int | None = None,
    deviation_top_k: int = 15,
    skip_sentiment: bool = False,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    reviews_path = resolve_reviews_path(project_root)
    print(f"Reviews source: {reviews_path}", file=sys.stderr)

    lid_to_city = load_master_listing_city(project_root)
    print(f"Master listings with city: {len(lid_to_city)}", file=sys.stderr)

    listing_docs = stream_aggregate_listing_documents(reviews_path, chunksize, lid_to_city)
    print(f"Aggregated listing documents: {len(listing_docs)}", file=sys.stderr)

    listing_docs = sample_listings_if_requested(listing_docs, max_listings)
    if max_listings:
        print(f"After --max-listings sample: {len(listing_docs)}", file=sys.stderr)

    vec, listing_ids, cities, X = fit_listing_tfidf(
        listing_docs,
        lid_to_city,
        max_features=max_features_listing,
        min_df=min_df_listing,
        max_df=max_df_listing,
    )
    vocab = vec.get_feature_names_out()
    # Output dir may have been moved/deleted during a long fit_transform; ensure it exists before any writes.
    out_dir.mkdir(parents=True, exist_ok=True)
    save_npz(out_dir / "listing_tfidf_matrix.npz", X)
    write_json(out_dir / "listing_tfidf_vocabulary.json", list(vocab))

    meta = pd.DataFrame(
        {
            "listing_id": listing_ids,
            "City": cities,
            "n_chars": [len(listing_docs[i]) for i in listing_ids],
            "n_reviews_concatenated": [listing_docs[i].count("\n") + 1 for i in listing_ids],
        }
    )
    meta.to_csv(out_dir / "listing_documents_meta.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame({"row_index": np.arange(len(listing_ids)), "listing_id": listing_ids}).to_csv(
        out_dir / "listing_tfidf_row_index.csv",
        index=False,
        encoding="utf-8-sig",
    )

    dev_df = listing_city_deviations(X, listing_ids, cities, vocab, top_k=deviation_top_k)
    dev_df.to_csv(out_dir / "listing_city_deviation_terms.csv", index=False, encoding="utf-8-sig")

    city_texts = city_corpus_from_listing_docs(listing_docs, lid_to_city)
    cvec, Xc, cities_sorted = fit_city_corpus_tfidf(city_texts, max_features=max_features_city)
    cvocab = cvec.get_feature_names_out()
    save_npz(out_dir / "city_corpus_tfidf_matrix.npz", Xc)
    write_json(out_dir / "city_corpus_tfidf_vocabulary.json", list(cvocab))
    pd.DataFrame({"row_index": np.arange(len(cities_sorted)), "City": cities_sorted}).to_csv(
        out_dir / "city_corpus_tfidf_rows.csv",
        index=False,
        encoding="utf-8-sig",
    )
    city_terms = city_top_terms_table(Xc, cities_sorted, cvocab, top_n=30)
    city_terms.to_csv(out_dir / "city_corpus_top_terms.csv", index=False, encoding="utf-8-sig")

    if not skip_sentiment:
        sent = sentiment_by_city_stream(reviews_path, chunksize, lid_to_city)
        sent.to_csv(out_dir / "city_sentiment_summary.csv", index=False, encoding="utf-8-sig")

    print(f"Wrote text features under {out_dir}", file=sys.stderr)
