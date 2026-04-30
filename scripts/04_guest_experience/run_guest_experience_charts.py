"""Rebuild guest-experience Q1–Q4 charts from committed CSVs under ``results/04_guest_experience``.

Loads summaries via ``load_data`` and renders plots via ``execute_python_code``
(toolkit escape hatch: grouped / horizontal bars not covered by ``create_visualization``).

Outputs PNGs under ``reports/figures/04_guest_experience/``.

Run:
    python scripts/04_guest_experience/run_guest_experience_charts.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("MPLCONFIGDIR", ".cache/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", ".cache")
os.environ.setdefault("MPLBACKEND", "Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import mba706_toolkit as mba

RESULTS_GE = PROJECT_ROOT / "results" / "04_guest_experience"
FIG_DIR = PROJECT_ROOT / "reports" / "figures" / "04_guest_experience"


def _posix(p: Path) -> str:
    return str(p.resolve().as_posix())


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    q1_path = RESULTS_GE / "q1_review_complaints" / "q1_complaint_cue_rate_by_city.csv"
    q2_path = RESULTS_GE / "q2_five_star_drivers" / "q2_subscore_importance_ranking.csv"
    q3_path = RESULTS_GE / "q3_operational_investments" / "q3_operational_signal_assoc.csv"
    q4_path = RESULTS_GE / "q4_top_performer_praise" / "q4_term_lift_top_vs_other.csv"

    for path in (q1_path, q2_path, q3_path, q4_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing input CSV: {path.relative_to(PROJECT_ROOT)}")

    mba.load_data(_posix(q1_path), dataset_name="gx_q1")
    mba.load_data(_posix(q2_path), dataset_name="gx_q2")
    mba.load_data(_posix(q3_path), dataset_name="gx_q3")
    mba.load_data(_posix(q4_path), dataset_name="gx_q4")

    out_q1 = _posix(FIG_DIR / "q1_complaint_cue_rate_by_city.png")
    out_q2 = _posix(FIG_DIR / "q2_subscore_drivers_rf_logistic.png")
    out_q3 = _posix(FIG_DIR / "q3_operational_signals_mean_rating.png")
    out_q4 = _posix(FIG_DIR / "q4_term_lift_top_performers.png")

    r_q1 = mba.execute_python_code(
        code=f'''
df = _data_store["gx_q1"].sort_values("share_complaint_cue", ascending=True)
fig, ax = plt.subplots(figsize=(8, 4))
ax.barh(df["City"], df["share_complaint_cue"] * 100, color="#2c7fb8")
ax.set_xlabel("Share of reviews with complaint cues (%)")
ax.set_title("Q1 — Complaint cue rate by city (higher = more problem language in text)")
mx = float((df["share_complaint_cue"] * 100).max())
ax.set_xlim(0, mx * 1.15 if mx > 0 else 1)
for i, v in enumerate(df["share_complaint_cue"] * 100):
    ax.text(float(v) + 0.2, i, f"{{v:.1f}}%", va="center", fontsize=9)
plt.tight_layout()
plt.savefig("{out_q1}", dpi=150, bbox_inches="tight")
plt.close(fig)
''',
        description="Q1 horizontal bar: complaint cue rate by city",
    )
    if r_q1.get("status") != "success":
        raise RuntimeError(r_q1)

    r_q2 = mba.execute_python_code(
        code=f'''
q2 = _data_store["gx_q2"]
label_map = {{
    "review_scores_cleanliness": "Cleanliness",
    "review_scores_checkin": "Check-in",
    "review_scores_communication": "Communication",
    "review_scores_location": "Location",
}}
q2 = q2.copy()
q2["dimension"] = q2["feature"].map(label_map)

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
x = range(len(q2))
axes[0].bar(x, q2["rf_importance"], color="#3182bd")
axes[0].set_xticks(list(x))
axes[0].set_xticklabels(q2["dimension"], rotation=25, ha="right")
axes[0].set_ylabel("RF feature importance")
axes[0].set_title("Random forest — predicting high overall rating")

axes[1].bar(x, q2["logistic_coef"], color="#31a354")
axes[1].set_xticks(list(x))
axes[1].set_xticklabels(q2["dimension"], rotation=25, ha="right")
axes[1].set_ylabel("Logistic coefficient")
axes[1].set_title("Logistic regression — same target")

fig.suptitle("Q2 — Guest experience dimensions vs overall ≥ 4.9", y=1.02, fontsize=12)
plt.tight_layout()
plt.savefig("{out_q2}", dpi=150, bbox_inches="tight")
plt.close(fig)
''',
        description="Q2 dual bar charts: RF importance vs logistic coefficients",
    )
    if r_q2.get("status") != "success":
        raise RuntimeError(r_q2)

    r_q3 = mba.execute_python_code(
        code=f'''
q3 = _data_store["gx_q3"]
signals = [
    "self_checkin_amenity",
    "keypad_lockbox",
    "cleaning_fee_listed",
    "instant_bookable_flag",
]
q3_sub = q3[q3["signal"].isin(signals)].copy()
pivot = q3_sub.pivot(index="signal", columns="flag", values="mean_overall_rating")
pivot = pivot.reindex(signals)
pivot.columns = ["Flag False", "Flag True"]
pretty = {{
    "self_checkin_amenity": "Self check-in (amenity text)",
    "keypad_lockbox": "Keypad / lockbox / smart lock",
    "cleaning_fee_listed": "Cleaning (amenity text)",
    "instant_bookable_flag": "Instant bookable",
}}
pivot.index = pivot.index.map(lambda s: pretty.get(s, s))

ax = pivot.plot(kind="bar", figsize=(9, 4), color=["#fc9272", "#3182bd"], edgecolor="black")
ax.set_ylabel("Mean overall review score")
ax.set_xlabel("")
ax.set_title("Q3 — Mean overall rating by listing flag (associative; not causal)")
ax.legend(title="")
plt.xticks(rotation=20, ha="right")
plt.tight_layout()
plt.savefig("{out_q3}", dpi=150, bbox_inches="tight")
plt.close(ax.figure)
''',
        description="Q3 grouped bars: mean overall rating by operational flags",
    )
    if r_q3.get("status") != "success":
        raise RuntimeError(r_q3)

    r_q4 = mba.execute_python_code(
        code=f'''
q4 = _data_store["gx_q4"]
top = q4.sort_values("lift_top_vs_other", ascending=False).head(18).iloc[::-1]

fig, ax = plt.subplots(figsize=(7, 6))
ax.barh(top["term"].astype(str), top["lift_top_vs_other"], color="#756bb1")
ax.set_xlabel("Lift (top quartile vs other + 1 smoothing)")
ax.set_title("Q4 — Distinctive review terms among highest-rated listings")
plt.tight_layout()
plt.savefig("{out_q4}", dpi=150, bbox_inches="tight")
plt.close(fig)
''',
        description="Q4 horizontal bar: term lift top vs other performers",
    )
    if r_q4.get("status") != "success":
        raise RuntimeError(r_q4)

    print(f"Saved charts under {FIG_DIR.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
