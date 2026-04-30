"""
Hierarchical text mining entry point (listing-level + city-level corpora).

Methodology: scripts/models/text_analysis/text_analytics_readme.md
Outputs: results/04_guest_experience/text_features/

Example:
  python scripts/models/text_analysis/run_hierarchical_text_mining.py
  python scripts/models/text_analysis/run_hierarchical_text_mining.py --max-listings 2000 --skip-sentiment
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_USE_SHM"] = "0"
os.environ["MPLCONFIGDIR"] = ".cache/matplotlib"
os.environ["XDG_CACHE_HOME"] = ".cache"
os.environ["MPLBACKEND"] = "Agg"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from text_mining_core import run_pipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Listing- and city-level TF-IDF + sentiment (chunked reviews, master city map)."
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=PROJECT_ROOT / "results" / "04_guest_experience" / "text_features",
        help="Directory for .npz / .json / CSV outputs",
    )
    p.add_argument("--chunksize", type=int, default=200_000, help="Rows per read_csv chunk")
    p.add_argument("--max-features-listing", type=int, default=8000)
    p.add_argument("--min-df-listing", type=int, default=10)
    p.add_argument("--max-df-listing", type=float, default=0.85)
    p.add_argument("--max-features-city", type=int, default=4000)
    p.add_argument(
        "--max-listings",
        type=int,
        default=None,
        help="Optional random subsample of listings (seed=42) for dry runs",
    )
    p.add_argument("--deviation-top-k", type=int, default=15)
    p.add_argument("--skip-sentiment", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(
        project_root=PROJECT_ROOT,
        out_dir=args.out_dir,
        chunksize=args.chunksize,
        max_features_listing=args.max_features_listing,
        min_df_listing=args.min_df_listing,
        max_df_listing=args.max_df_listing,
        max_features_city=args.max_features_city,
        max_listings=args.max_listings,
        deviation_top_k=args.deviation_top_k,
        skip_sentiment=args.skip_sentiment,
    )


if __name__ == "__main__":
    main()
