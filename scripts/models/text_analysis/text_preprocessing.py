"""
Text preprocessing for the hierarchical TF-IDF pipeline.

The review cleaner (run_full_review_cleaning.py) already lowercases text,
strips HTML, and normalizes whitespace on comments_clean. Here we add the
standard text-mining stack: punctuation removal and stemming; stopwords are
removed at vectorization time (english stop list via TfidfVectorizer).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from nltk.stem import PorterStemmer

_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")


def normalize_surface(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace (alphanumeric tokens only)."""
    if text is None:
        return ""
    s = str(text).lower()
    s = _NON_ALNUM.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_stem_analyzer(stemmer: PorterStemmer | None = None) -> Callable[[str], Iterable[str]]:
    """
    Return an *analyzer* for TfidfVectorizer(analyzer=...).

    Tokens are stemmed; pass stop_words='english' on the vectorizer.
    """
    ps = stemmer or PorterStemmer()

    def _analyze(raw: str) -> Iterable[str]:
        s = normalize_surface(raw)
        for tok in s.split():
            if len(tok) < 2:
                continue
            yield ps.stem(tok)

    return _analyze
