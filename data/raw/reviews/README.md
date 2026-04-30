This folder is reserved for the raw Airbnb review datasets.

Expected filenames (snake_case, matches the rest of the project):
- `reviews_hawaii.csv`
- `reviews_los_angeles.csv`
- `reviews_nashville.csv`
- `reviews_new_york.csv`
- `reviews_san_francisco.csv`

These raw files are intentionally ignored by Git because they are too large to store in the repository.

The cleaning pipeline that consumes them is `scripts/cleaning/reviews/run_full_review_cleaning.py`.
