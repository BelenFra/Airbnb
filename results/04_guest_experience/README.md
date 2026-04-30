# Guest experience — research outputs

Structured like `results/01_market_analysis/`: one folder per question with `q*_summary.md` and CSV evidence.

| Folder | Question |
|--------|----------|
| `q1_review_complaints/` | What do guests complain about in reviews? By city and property type? |
| `q2_five_star_drivers/` | Which cleanliness / check-in / communication / location scores associate with ≥4.9 overall? |
| `q3_operational_investments/` | Operational proxies (amenities, instant book) vs review outcomes |
| `q4_top_performer_praise/` | Language that distinguishes top-quartile listings (TF‑IDF deviations) |
| `text_features/` | sparse matrices and vocabulary from `scripts/text_analysis/run_hierarchical_text_mining.py` |

**Scripts**

- Text mining: `scripts/text_analysis/run_hierarchical_text_mining.py`
- This synthesis: `scripts/04_guest_experience/run_guest_experience_questions.py`
