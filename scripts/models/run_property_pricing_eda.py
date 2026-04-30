#!/usr/bin/env python3
"""Targeted Property/Pricing EDA per property_pricing_modeling_spec.txt.
Does not train models or modify master_data.csv."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "master_data.csv"
SPEC_PATH = ROOT / "property_pricing_modeling_spec.txt"
OUT_DIR = ROOT / "eda"

# Spec §4 occupancy proxy check (material disagreement)
PROXY_DELTA_THRESHOLD = 0.01


def skewness(series: pd.Series) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 3:
        return float("nan")
    m = s.mean()
    v = s.var(ddof=0)
    if v <= 0:
        return 0.0
    return float(((s - m) ** 3).mean() / (v ** 1.5))


def parse_amenity_list(raw) -> tuple[bool, int | None, str | None]:
    if pd.isna(raw):
        return False, None, "null_like"
    x = str(raw).strip()
    if not x:
        return False, None, "empty"
    try:
        val = json.loads(x)
        if isinstance(val, list):
            return True, len(val), None
        return False, None, f"parsed_non_list:{type(val).__name__}"
    except json.JSONDecodeError as e:
        return False, None, f"json_error:{e.msg[:80]}"


def bath_label(x: float) -> str:
    if pd.isna(x):
        return "missing"
    if x <= 1:
        return "(0,1]"
    if x <= 2:
        return "(1,2]"
    if x <= 3:
        return "(2,3]"
    return "(3+]"


def apply_row_filters(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Sequential removal per spec §4; each mask evaluated on the current working frame."""
    n0 = len(df)
    dup_ids = int(df["id"].duplicated(keep=False).sum())
    assert dup_ids == 0, f"duplicate listing ids detected: {dup_ids}"

    work = df.copy()
    audit: list[dict] = []
    step_no = 0

    def step(name: str, mask_drop: pd.Series) -> None:
        nonlocal work, step_no
        step_no += 1
        dropped = mask_drop.reindex(work.index).fillna(False)
        removed = int(dropped.sum())
        work = work.loc[~dropped].copy()
        n_after = len(work)
        audit.append(
            {
                "step": step_no,
                "rule": name,
                "rows_removed_this_step": removed,
                "rows_remaining_cumulative": n_after,
                "pct_of_start_removed_cumulative": round(100 * (n0 - n_after) / n0, 6),
            }
        )

    step("price <= 0 (spec §4: exclude from log-price estimation)", work["price"] <= 0)

    step(
        "bedrooms >= 15 (spec §4 guardrail)",
        pd.to_numeric(work["bedrooms"], errors="coerce").fillna(0) >= 15,
    )

    step(
        "bathrooms > 10 (spec §4 guardrail)",
        pd.to_numeric(work["bathrooms"], errors="coerce").fillna(0) > 10,
    )

    step(
        "accommodates > 16 (spec §4 guardrail)",
        pd.to_numeric(work["accommodates"], errors="coerce").fillna(0) > 16,
    )

    acc = pd.to_numeric(work["accommodates"], errors="coerce")
    bd = pd.to_numeric(work["bedrooms"], errors="coerce").fillna(0)
    step(
        "joint: bedrooms > accommodates + 5 (implausible)",
        (bd > (acc.fillna(0) + 5)).fillna(False),
    )

    step(
        "joint: bedrooms >= 10 AND accommodates <= 2 (implausible)",
        ((bd >= 10) & (acc.fillna(0) <= 2)).fillna(False),
    )

    return work, audit


def property_type_bucket(s: pd.Series, top_k: int = 12) -> pd.Series:
    s = s.fillna("__missing__").astype(str)
    top = s.value_counts().head(top_k).index
    out = np.where(s.isin(top), s, "__other_property_type__")
    return pd.Series(out, index=s.index, dtype="object")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df_full = pd.read_csv(DATA_PATH, low_memory=False)
    n_source = len(df_full)

    filtered, audit_records = apply_row_filters(df_full)
    filtered = filtered.assign(
        log_price=np.log(filtered["price"].astype(float)),
        accommodates_numeric=pd.to_numeric(filtered["accommodates"], errors="coerce"),
    )

    # --- Filter accounting files ---
    acct_lines = [
        "property_pricing_filter_accounting",
        f"source_rows={n_source}",
        f"master_data_csv={DATA_PATH}",
        f"spec_reference={SPEC_PATH}",
        "",
        "Each step applies to the frame remaining after prior steps.",
        "",
    ]
    audit_df = pd.DataFrame(audit_records)
    for _, row in audit_df.iterrows():
        acct_lines.append(
            f"step_{int(row['step'])}: {row['rule']} | "
            f"removed_this_step={int(row['rows_removed_this_step'])} | "
            f"remaining_cumulative={int(row['rows_remaining_cumulative'])} | "
            f"pct_removed_vs_original_start={row['pct_of_start_removed_cumulative']}"
        )
    acct_lines.extend(["", f"final_analytic_rows={len(filtered)}"])
    acct_lines.append(
        f"duplicate_id_rows_in_source={int(df_full['id'].duplicated(keep=False).sum())} (expect 0)"
    )

    (OUT_DIR / "property_pricing_filter_accounting.txt").write_text("\n".join(acct_lines) + "\n", encoding="utf-8")
    audit_df.to_csv(OUT_DIR / "property_pricing_filter_accounting_steps.csv", index=False)

    sent = [
        "[Sentinel QA on FULL source sample — informational, spec §4 recode rules; rows not dropped by default]",
        f"host_has_profile_pic == 'f' count: {(df_full['host_has_profile_pic'].astype(str) == 'f').sum()}",
        f"host_identity_verified == 'f' count: {(df_full['host_identity_verified'].astype(str) == 'f').sum()}",
    ]
    for col in ["host_is_superhost", "has_availability"]:
        u = int(df_full[col].astype(str).str.strip().eq("unknown").sum())
        sent.append(f"{col} == 'unknown' count: {u}")
    sent.append("")
    (OUT_DIR / "property_pricing_sentinel_counts.txt").write_text("\n".join(sent) + "\n", encoding="utf-8")

    # --- Build summary ---
    summary_lines = [
        "PROPERTY / PRICING — FOCUSED EDA (pricing block only)",
        f"Artifacts directory: {OUT_DIR.relative_to(ROOT)}",
        "",
        "## 1) Row filters applied (transparent accounting)",
        f"Starting rows (master_data.csv): {n_source}",
    ]
    for _, row in audit_df.iterrows():
        summary_lines.append(
            f"  Step {int(row['step'])}: removed {int(row['rows_removed_this_step'])} — {row['rule']}"
        )
    summary_lines.append(f"Remaining analytic rows: {len(filtered)}")
    summary_lines.append("See property_pricing_filter_accounting.txt and property_pricing_filter_accounting_steps.csv.")

    # Target validation
    p_all = pd.to_numeric(df_full["price"], errors="coerce")

    summary_lines.extend(
        [
            "",
            "## 2) Price target validation",
            "### price — FULL numeric sample",
            p_all.describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999]).round(4).to_string(),
            f"skewness(full price): {skewness(p_all):.6f}",
            "",
            "### price — ANALYTIC (post row filters)",
            pd.to_numeric(filtered["price"], errors="coerce").describe(
                percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
            ).round(4).to_string(),
            f"skewness(filtered price): {skewness(filtered['price']):.6f}",
            "",
            "### log(price) — ANALYTIC (post filters)",
            filtered["log_price"]
            .describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
            .round(6).to_string(),
            f"skewness(log_price filtered): {skewness(filtered['log_price']):.6f}",
            "",
            f"Heavy tail: filtered top-1% price threshold = {filtered['price'].quantile(0.99):.2f} USD (n={(filtered['price'] >= filtered['price'].quantile(0.99)).sum()} rows at/above cutoff).",
            "",
            "### Commentary (skew / tail)",
            f"- Raw price skewness (~{skewness(p_all):.2f}) shows a heavy right tail; log(price) skewness (~{skewness(filtered['log_price']):.2f}) is much closer to symmetric — consistent with adopting log(price) as the regression target.",
            "- Extreme displayed nightly rates remain in filtered data at high quantiles; tree ensembles can handle heavy tails yet benefit from monitoring top-coded sensitivity later.",
            "",
            "## 3) Descriptive log(price) summaries (filtered sample)",
            "CSV tables saved with mean/median/count for modeling reference.",
        ]
    )

    gb_city = (
        filtered.groupby("City", observed=True)["log_price"].agg(["count", "mean", "std", "median"]).sort_index()
    )
    gb_rt = (
        filtered.groupby("room_type", observed=True)["log_price"].agg(["count", "mean", "std", "median"])
    )

    bd_bins = filtered.copy()
    bd_bins["bedrooms_bin"] = pd.cut(
        pd.to_numeric(bd_bins["bedrooms"], errors="coerce"),
        bins=[-0.01, 0, 1, 2, 3, 4, 50],
        labels=["0", "1", "2", "3", "4", "5+"],
    )
    gb_bed = bd_bins.groupby("bedrooms_bin", observed=True)["log_price"].agg(["count", "mean", "median"])

    acc_cat = pd.cut(
        filtered["accommodates_numeric"],
        bins=[-np.inf, 2, 4, 6, 8, np.inf],
        labels=["<=2", "3-4", "5-6", "7-8", ">=9"],
    )
    gb_acc = filtered.assign(accommodates_bin=acc_cat).groupby("accommodates_bin", observed=True)["log_price"].agg(
        ["count", "mean", "median"]
    )

    b = pd.to_numeric(filtered["bathrooms"], errors="coerce")
    gb_bath = filtered.assign(bathroom_bucket=b.map(bath_label)).groupby("bathroom_bucket", observed=True)[
        "log_price"
    ].agg(["count", "mean", "median"])

    filtered_pt = filtered.assign(property_type_group=property_type_bucket(filtered["property_type"]))
    gb_pt = (
        filtered_pt.groupby("property_type_group", observed=True)["log_price"]
        .agg(["count", "mean", "median"])
        .sort_values("count", ascending=False)
    )

    gb_city.to_csv(OUT_DIR / "summary_logprice_by_city.csv")
    gb_rt.to_csv(OUT_DIR / "summary_logprice_by_room_type.csv")
    gb_bed.to_csv(OUT_DIR / "summary_logprice_by_bedrooms_bin.csv")
    gb_acc.to_csv(OUT_DIR / "summary_logprice_by_accommodates_bin.csv")
    gb_bath.to_csv(OUT_DIR / "summary_logprice_by_bathrooms_bucket.csv")
    gb_pt.to_csv(OUT_DIR / "summary_logprice_by_property_type_top12_other.csv")

    gx = (
        filtered.groupby(["City", "room_type"], observed=True)["log_price"]
        .agg(["count", "mean", "median"])
        .reset_index()
    )
    gx.to_csv(OUT_DIR / "summary_logprice_city_x_room_type.csv")
    pivot_mean = gx.pivot(index="City", columns="room_type", values="mean")
    pivot_mean.round(6).to_csv(OUT_DIR / "summary_city_x_room_mean_logprice_wide.csv")

    gap_notes: list[str] = []
    if "Entire home/apt" in pivot_mean.columns and "Private room" in pivot_mean.columns:
        gap_notes.append(
            "Mean log(price): Entire home/apt minus Private room (approx multiplicative gap on exponentiation):"
        )
        gap_series = pivot_mean["Entire home/apt"] - pivot_mean["Private room"]
        gap_series.round(6).rename("gap_mean_log_price").to_csv(OUT_DIR / "summary_city_entire_minus_private_gap.csv")
        for cty in sorted(gap_series.index):
            v = gap_series.loc[cty]
            gap_notes.append(f"  - {cty}: Δ(mean log price) = {v:.4f}")
    else:
        gap_notes.append("Could not compute entire-home minus private-room gap (missing column names).")

    summary_lines.extend(
        [
            "",
            "## 4) City × room_type — entire home vs private room",
            *gap_notes,
            "",
            "- Cross-city read: Δ mean log price differences near ~0.2–0.5 imply roughly +22%–65% nominal premia via exp approximation; inspect summary_city_entire_minus_private_gap.csv.",
            "",
            "### Cross-city similarity",
            "- If Δ gaps cluster tightly, premiums are homogeneous across metros; divergence suggests market-specific segmentation (City × room_type interactions) matters for boosted trees.",
        ]
    )

    # Amenities (full raw file)
    results = df_full["amenities"].apply(parse_amenity_list)
    ok = results.apply(lambda t: t[0])
    counts = results.apply(lambda t: t[1])
    errs = results.apply(lambda t: t[2])

    ami_df = pd.DataFrame({"parse_ok": ok, "amenity_count": counts, "parse_issue": errs})
    parse_success_rate = float(ami_df["parse_ok"].mean())
    ami_fail = ami_df[~ami_df["parse_ok"]]["parse_issue"].value_counts(dropna=False).head(20)

    ami_df.to_csv(OUT_DIR / "amenities_parse_rowflags_full_sample.csv", index=False)
    pd.DataFrame({"parse_success_rate": [parse_success_rate], "failure_rows": [(~ok).sum()]}).to_csv(
        OUT_DIR / "amenities_parse_summary_metrics.csv",
        index=False,
    )
    ami_fail.to_frame(name="count").to_csv(OUT_DIR / "amenities_parse_top_failure_reasons.csv")

    dist = ami_df.loc[ami_df["parse_ok"], "amenity_count"].describe()
    with open(OUT_DIR / "amenities_parse_distribution.txt", "w", encoding="utf-8") as fho:
        fho.write("amenities JSON parse smoke test\n")
        fho.write(f"parse_success_rate: {parse_success_rate:.8f}\n")
        fho.write("amenity_count (successful parses only):\n")
        fho.write(dist.round(4).to_string())

    summary_lines.extend(
        [
            "",
            "## 5) Amenities smoke test",
            f"- Parse success rate (strict JSON array): {parse_success_rate:.8f}",
            f"- Rows failing strict parse: {(~ok).sum()} — review amenities_parse_rowflags_full_sample.csv",
            "- amenity-count distribution printed in amenities_parse_distribution.txt",
        ]
    )

    avail = pd.to_numeric(df_full["availability_365"], errors="coerce")
    proxy = pd.to_numeric(df_full["occupancy_rate_proxy"], errors="coerce")
    implied_occ = ((365 - avail) / 365.0).replace([-np.inf, np.inf], np.nan)
    abs_gap = (proxy - implied_occ).abs()

    mism = df_full.loc[abs_gap > PROXY_DELTA_THRESHOLD].copy()
    mism = mism.assign(
        calendar_implied_occupancy_rate=implied_occ.loc[mism.index],
        abs_gap_occupancy_proxy_minus_calendar=(
            proxy.loc[mism.index] - implied_occ.loc[mism.index]
        ).abs(),
        signed_gap_occupancy_proxy_minus_calendar=(
            proxy.loc[mism.index] - implied_occ.loc[mism.index]
        ),
    )

    mism.to_csv(OUT_DIR / "occupancy_proxy_calendar_mismatch_rows.csv", index=False)

    pd.DataFrame(
        [
            {
                "threshold_abs_gap": PROXY_DELTA_THRESHOLD,
                "mismatch_row_count": len(mism),
                "share_of_rows": round(len(mism) / len(df_full), 10),
                "max_abs_gap_observed": float(abs_gap.max()),
            }
        ]
    ).to_csv(OUT_DIR / "occupancy_proxy_mismatch_metrics.csv", index=False)

    summary_lines.extend(
        [
            "",
            "## 6) Occupancy proxy vs calendar implied rate",
            f"- Threshold: |occupancy_rate_proxy - (365-availability_365)/365| > {PROXY_DELTA_THRESHOLD}",
            f"- Rows flagged: {len(mism)} ({100 * len(mism) / len(df_full):.4f}% of raw file)",
            "- Saved flagged rows → occupancy_proxy_calendar_mismatch_rows.csv",
            "",
            "## 7) Cardinality QA (listing structure)",
            "See cardinality_city_room_property_type.csv for City × room_type × property_type counts.",
        ]
    )

    card = (
        df_full.groupby(["City", "room_type", "property_type"], observed=True)
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
    )
    card.to_csv(OUT_DIR / "cardinality_city_room_property_type.csv", index=False)

    rev = filtered.loc[filtered["number_of_reviews"] > 0]
    if len(rev) > 0:
        rev[["log_price", "review_scores_rating"]].describe().to_csv(
            OUT_DIR / "summary_logprice_and_review_rating_filtered_reviews_gt0.csv"
        )

    summary_lines.extend(
        [
            "",
            "## 8) Output index",
            " - property_pricing_eda_summary.txt (this file)",
            " - property_pricing_filter_accounting.txt",
            " - property_pricing_filter_accounting_steps.csv",
            " - property_pricing_sentinel_counts.txt",
            " - summary_logprice_*.csv, summary_city_*.csv",
            " - amenities_parse_*.csv / amenities_parse_distribution.txt",
            " - occupancy_proxy_calendar_mismatch_rows.csv, occupancy_proxy_mismatch_metrics.csv",
            " - cardinality_city_room_property_type.csv",
        ]
    )

    (OUT_DIR / "property_pricing_eda_summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
