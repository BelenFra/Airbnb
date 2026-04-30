#!/usr/bin/env python3
"""Build Property/Pricing modeling CSV from master_data.csv.

Compliance: property_pricing_modeling_spec.txt
Structural filters mirrored from scripts/run_property_pricing_eda.py.

Does not train models or modify master_data.csv.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master_data.csv"
SPEC_REF = ROOT / "property_pricing_modeling_spec.txt"
OUT_DIR = ROOT / "modeling"
PROXY_MISMATCH_THRESHOLD = 0.01

TARGETS = ("price", "log_price")
LINEAGE = ("listing_id", "host_id")
AMENITY_FLAG_COLS = (
    "pool",
    "parking",
    "workspace",
    "wifi",
    "kitchen",
    "air_conditioning",
    "self_check_in",
    "washer",
    "dryer",
    "hot_tub",
    "pets_allowed",
)


def apply_structural_row_filters(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Identical sequencing to scripts/run_property_pricing_eda.py."""
    n0 = len(df)
    if int(df["id"].duplicated(keep=False).sum()):
        raise ValueError("Duplicate listing ids in master.")

    work = df.copy()
    audit: list[dict] = []
    step_no = 0

    def step(name: str, mask_drop: pd.Series) -> None:
        nonlocal work, step_no
        step_no += 1
        dropped = mask_drop.reindex(work.index).fillna(False)
        removed = int(dropped.sum())
        work = work.loc[~dropped].copy()
        audit.append(
            {
                "step": step_no,
                "rule": name,
                "rows_removed_this_step": removed,
                "rows_remaining_cumulative": len(work),
                "pct_removed_vs_start": round(100 * (n0 - len(work)) / n0, 6),
            }
        )

    step("price <= 0", work["price"] <= 0)
    step(
        "bedrooms >= 15",
        pd.to_numeric(work["bedrooms"], errors="coerce").fillna(0) >= 15,
    )
    step(
        "bathrooms > 10",
        pd.to_numeric(work["bathrooms"], errors="coerce").fillna(0) > 10,
    )
    step(
        "accommodates > 16",
        pd.to_numeric(work["accommodates"], errors="coerce").fillna(0) > 16,
    )
    acc = pd.to_numeric(work["accommodates"], errors="coerce")
    bd = pd.to_numeric(work["bedrooms"], errors="coerce").fillna(0)
    step(
        "joint: bedrooms > accommodates + 5",
        (bd > (acc.fillna(0) + 5)).fillna(False),
    )
    step(
        "joint: bedrooms >= 10 AND accommodates <= 2",
        ((bd >= 10) & (acc.fillna(0) <= 2)).fillna(False),
    )
    return work, audit


def parse_amenity_strings(raw: object) -> tuple[bool, list[str]]:
    if pd.isna(raw):
        return False, []
    text = str(raw).strip()
    if not text:
        return False, []
    try:
        val = json.loads(text)
        if isinstance(val, list):
            return True, [str(it).strip().lower() for it in val if not pd.isna(it)]
        return False, []
    except json.JSONDecodeError:
        return False, []


def derive_amenity_flags(strings: Iterable[str]) -> dict[str, bool]:
    seq = tuple(strings)

    amenity_pool = any(
        (not any(tok in it for tok in ("no pool", "without pool", "pool unavailable"))) and ("pool" in it)
        for it in seq
    )

    amenity_parking = any(
        any(k in it for k in ("parking", "garage", "carport")) or "free parking" in it for it in seq
    )

    amenity_wifi = any(("wifi" in it) or ("wi-fi" in it) or ("wireless internet" in it) for it in seq)

    amenity_workspace = any(("workspace" in it) or ("laptop friendly" in it) for it in seq)

    amenity_kitchen = any("kitchen" in it for it in seq)

    amenity_air_conditioning = False
    for it in seq:
        if any(
            phrase in it
            for phrase in (
                "no air conditioning",
                "does not include air conditioning",
                "central air unavailable",
            )
        ):
            continue
        if any(
            phrase in it
            for phrase in ("air conditioning", "central air", "portable air conditioning")
        ):
            amenity_air_conditioning = True

    amenity_self_check_in = any(
        any(
            phrase in it
            for phrase in ("self check-in", "self check in", "keypad", "lockbox", "smart lock")
        )
        for it in seq
    )

    amenity_washer = any(("washing machine" in it) or (it.strip() == "washer") for it in seq)

    amenity_dryer = False
    for it in seq:
        if "hair dryer" in it:
            continue
        if "dryer" in it:
            amenity_dryer = True

    amenity_hot_tub = any(("hot tub" in it) or ("jacuzzi" in it) for it in seq)

    pos_tokens = (
        "pets allowed",
        "allows pets",
        "pet friendly",
        "dogs allowed",
        "cats allowed",
        "pets live on this property",
    )
    neg_tokens = (
        "no pets",
        "pets not allowed",
        "not suitable for pets",
        "pets not welcome",
        "does not accommodate pets",
    )

    pets_pos = any(any(t in item for t in pos_tokens) for item in seq)
    pets_neg = any(any(t in item for t in neg_tokens) for item in seq)

    amenity_pets_allowed = pets_pos and not pets_neg

    return {
        "pool": amenity_pool,
        "parking": amenity_parking,
        "workspace": amenity_workspace,
        "wifi": amenity_wifi,
        "kitchen": amenity_kitchen,
        "air_conditioning": amenity_air_conditioning,
        "self_check_in": amenity_self_check_in,
        "washer": amenity_washer,
        "dryer": amenity_dryer,
        "hot_tub": amenity_hot_tub,
        "pets_allowed": amenity_pets_allowed,
    }


def coerce_host_superhost(series: pd.Series) -> pd.Series:

    def one(x):
        if pd.isna(x):
            return pd.NA
        s = str(x).strip()
        if s == "True":
            return True
        if s == "False":
            return False
        return pd.NA

    return pd.Series(series.map(one), dtype=pd.BooleanDtype())


def occupancy_calendar_mismatch(df: pd.DataFrame) -> pd.Series:
    avail = pd.to_numeric(df["availability_365"], errors="coerce")
    proxy = pd.to_numeric(df["occupancy_rate_proxy"], errors="coerce")
    implied = (365 - avail) / 365.0
    gap = (proxy - implied).abs()
    return gap.fillna(0.0) > PROXY_MISMATCH_THRESHOLD


def exclusion_reason_lookup() -> dict[str, str]:
    return {
        "id": "Renamed listing_id for lineage.",
        "amenities": "Raw JSON replaced engineered amenity_count + binary investor flags.",
        "name": "Replaced engineered name_char_count.",
        "host_since": "Engineered → host_tenure_years anchored on last_scraped.",
        "host_is_superhost": "Replaced engineered host_is_superhost_clean booleans.",
        "last_scraped": "Used only for tenure; withheld from learner.",
        "estimated_revenue_l365d": "Exact equality revenue = price × occupancy (leakage).",
        "scrape_id": "Redundant with City in stitched master.",
        "unavailability_rate": "Linear redundancy versus availability_rate.",
        "listing_url": "Opaque URL withheld.",
        "picture_url": "Opaque URL withheld.",
        "host_url": "Opaque URL withheld.",
        "host_picture_url": "Opaque URL withheld.",
        "host_thumbnail_url": "Opaque URL withheld.",
        "source": "Effectively constant in master scrape.",
        "host_acceptance_rate": "Degenerate zeros (scraping artefact).",
        "host_response_rate": "Degenerate zeros.",
        "host_has_profile_pic": "Malformed literal 'f' pending repair.",
        "host_identity_verified": "Malformed literal 'f' pending repair.",
        "has_availability": "Dominant unknown strings.",
        "availability_30": "Occupancy strand omitted from hedonic nightly price learner.",
        "availability_60": "Occupancy strand omitted from hedonic nightly price learner.",
        "availability_90": "Occupancy strand omitted from hedonic nightly price learner.",
        "availability_365": "Used purely for QA guardrail; withheld from learner.",
        "availability_eoy": "Occupancy strand omitted from hedonic nightly price learner.",
        "availability_rate": "Occupancy strand omitted from nightly price learner.",
        "occupancy_rate_proxy": "Occupancy strand + QA mismatch guardrail driver.",
        "estimated_occupancy_l365d": "Potential endogeneity versus price.",
        "reviews_per_month": "Demand / outcome proxy.",
        "number_of_reviews": "Demand / outcome proxy.",
        "number_of_reviews_l30d": "Demand / outcome proxy.",
        "number_of_reviews_ltm": "Demand / outcome proxy.",
        "number_of_reviews_ly": "Demand / outcome proxy.",
        "first_review": "Temporal downstream metadata withheld.",
        "last_review": "Temporal downstream metadata withheld.",
        "calendar_last_scraped": "Operational scrape metadata withheld.",
        "review_scores_accuracy": "Downstream review block omitted baseline.",
        "review_scores_checkin": "Downstream review block omitted baseline.",
        "review_scores_cleanliness": "Downstream review block omitted baseline.",
        "review_scores_communication": "Downstream review block omitted baseline.",
        "review_scores_location": "Downstream review block omitted baseline.",
        "review_scores_rating": "Downstream review block omitted baseline.",
        "review_scores_value": "Downstream review block omitted baseline.",
        "description": "Long unstructured text withheld from matrix.",
        "neighborhood_overview": "Secondary prose withheld.",
        "neighbourhood": "Messy raw neighbourhood withheld (use *_cleansed).",
        "host_about": "Host prose withheld.",
        "host_location": "Self-reported geography withheld.",
        "host_name": "PII withheld.",
        "host_neighbourhood": "Messy ancillary label withheld.",
        "host_verifications": "Bulky unstructured list withheld.",
        "host_response_time": "Host attribute omitted baseline.",
    }


def describe_suppressed(master_cols: Iterable[str], exported_columns: Iterable[str]) -> list[tuple[str, str]]:
    reasons = exclusion_reason_lookup()
    exported = set(exported_columns)
    default_reason = "Not propagated to nightly pricing predictor matrix."

    rows: list[tuple[str, str]] = []
    for col in sorted(master_cols):
        if col == "id":
            rows.append((col, reasons["id"]))
            continue
        if col in exported:
            continue
        rows.append((col, reasons.get(col, default_reason)))
    return rows


def predictor_schema() -> tuple[str, ...]:
    return (
        (
            "accommodates",
            "bathrooms",
            "bathrooms_text",
            "bedrooms",
            "beds",
            "calculated_host_listings_count",
            "calculated_host_listings_count_entire_homes",
            "calculated_host_listings_count_private_rooms",
            "calculated_host_listings_count_shared_rooms",
            "City",
            "instant_bookable",
            "latitude",
            "longitude",
            "minimum_nights",
            "maximum_nights",
            "minimum_minimum_nights",
            "maximum_minimum_nights",
            "minimum_maximum_nights",
            "maximum_maximum_nights",
            "minimum_nights_avg_ntm",
            "maximum_nights_avg_ntm",
            "neighbourhood_cleansed",
            "neighbourhood_group_cleansed",
            "property_type",
            "room_type",
            "host_listings_count",
            "host_total_listings_count",
            "host_tenure_years",
            "name_char_count",
            "host_is_superhost_clean",
            "amenities_parse_ok",
            "amenity_count",
        )
        + AMENITY_FLAG_COLS
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(MASTER, low_memory=False)
    master_cols = tuple(raw.columns)
    mism_master_rows = int(occupancy_calendar_mismatch(raw).sum())

    filtered, structural_audit = apply_structural_row_filters(raw)
    mism_within = occupancy_calendar_mismatch(filtered)
    occupancy_guard_removed = int(mism_within.sum())
    modeled = filtered.loc[~mism_within].copy()

    modeled = modeled.rename(columns={"id": "listing_id"})

    prices = pd.to_numeric(modeled["price"], errors="coerce")
    if prices.le(0).any():
        raise ValueError("Non-positive prices after structural filters.")

    modeled["log_price"] = np.log(prices.astype(float))

    scrape_dt = pd.to_datetime(modeled["last_scraped"], errors="coerce")
    joined = pd.to_datetime(modeled["host_since"], errors="coerce")

    modeled["host_tenure_years"] = (
        ((scrape_dt - joined).dt.days.astype("Float64")).astype(float) / 365.25
    )

    modeled["name_char_count"] = modeled["name"].fillna("").astype(str).str.len()

    parsed = modeled["amenities"].apply(parse_amenity_strings)
    modeled["amenities_parse_ok"] = parsed.apply(lambda t: t[0])
    modeled["amenity_count"] = (
        parsed.apply(lambda t: float(len(t[1])))
        .where(modeled["amenities_parse_ok"])
        .astype("Float64")
        .fillna(0.0)
        .astype("float64")
    )

    amenities_flags = pd.DataFrame(
        parsed.apply(lambda t: derive_amenity_flags(t[1])).tolist(),
        index=modeled.index,
    )
    modeled = pd.concat([modeled, amenities_flags], axis=1)

    modeled["host_is_superhost_clean"] = coerce_host_superhost(modeled["host_is_superhost"])

    predictor_cols = predictor_schema()

    dataset = modeled[[*LINEAGE, *TARGETS, *predictor_cols]]

    predictor_count = len(predictor_cols)
    final_rows = len(dataset)

    dataset_path = OUT_DIR / "property_pricing_modeling_dataset.csv"

    dataset.to_csv(dataset_path, index=False)

    predictors_sorted = sorted(predictor_cols)

    incl_path = OUT_DIR / "property_pricing_predictors_included.txt"
    incl_path.write_text(
        "\n".join(
            [
                "PROPERTY / PRICING — INCLUDED PREDICTORS",
                "",
                "Non-predictors in CSV:",
                "- listing_id, host_id (lineage identifiers)",
                "- price, log_price (targets)",
                "",
                "Predictors only (candidate X columns): "
                + str(predictor_count),
                "",
                *predictors_sorted,
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exclusions = describe_suppressed(master_cols, dataset.columns)
    exclusions_path = OUT_DIR / "property_pricing_predictors_excluded.txt"
    exclusions_path.write_text(
        "\n".join(
            [
                "PROPERTY / PRICING — EXCLUSIONS RELATIVE TO master_data.csv",
                "",
                "column	reason",
            ]
            + [f"{col}\t{reason}" for col, reason in exclusions]
        )
        + "\n",
        encoding="utf-8",
    )

    flagged_parse_fail = int((~dataset["amenities_parse_ok"]).sum())

    summary_path = OUT_DIR / "property_pricing_dataset_preparation_summary.txt"

    summary_lines = [
        "PROPERTY / PRICING — DATASET PREPARATION SUMMARY",
        "",
        f"Script: {(Path(__file__).relative_to(ROOT)).as_posix()}",
        f"Spec anchor: {(SPEC_REF.relative_to(ROOT)).as_posix()}",
        "",
        "Row accounting",
        f"- Imported rows from master_data.csv: {len(raw)}",
    ]
    summary_lines.extend(
        f"- Step {record['step']}: {record['rule']} dropped {record['rows_removed_this_step']} "
        f"(running total remaining {record['rows_remaining_cumulative']})"
        for record in structural_audit
    )
    summary_lines.extend(
        [
            f"- Rows matching occupancy proxy QA guard after structural filtering: "
            f"{occupancy_guard_removed} (these rows removed — conservative cleanliness even though nightly-price "
            "learner excludes calendar fields outright).",
            f"- Master occupancy-proxy mismatch population (FYI): {mism_master_rows} rows flagged pre-filter.",
            "",
            f"FINAL_ROWS={final_rows}",
            f"PREDICTOR_COUNT={predictor_count}",
            "PRIMARY_TARGET=log_price (price retained for dashboards)",
            "",
            "Structural notes",
            "- City retained; scrape_id withheld as redundant.",
            "- Raw amenities suppressed; modeled via amenity_count + requested binary amenity_* flags.",
            f"- Parsed strictly via json.loads failures counted by amenities_parse_ok (failed rows: "
            f"{flagged_parse_fail}); booleans fallback FALSE via empty vectors; amenity_count coerced "
            "to 0 when parse fails for matrix completeness.",
            "- Review-history fields omitted outright (baseline hedonic spec).",
            "- Host rates + corrupt identity flags withheld until upstream repair.",
        ]
    )

    summary_lines.extend(
        [
            "",
            "Artifacts",
            f"- Modeling CSV: {(dataset_path.relative_to(ROOT)).as_posix()}",
            f"- Included predictors manifest: {(incl_path.relative_to(ROOT)).as_posix()}",
            f"- Excluded predictors manifest: {(exclusions_path.relative_to(ROOT)).as_posix()}",
            f"- Preparation summary (this duplication): {(summary_path.relative_to(ROOT)).as_posix()}",
        ]
    )

    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    master_set = set(master_cols)
    exported_same_name = master_set.intersection(dataset.columns)
    suppressed_set = {col for col, _ in exclusions}
    if suppressed_set.union(exported_same_name) != master_set:
        missing = master_set - suppressed_set.union(exported_same_name)
        extra = suppressed_set.union(exported_same_name) - master_set
        raise RuntimeError(f"Accounting mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    if suppressed_set.intersection(exported_same_name):
        raise RuntimeError("Suppressed and exported overlaps detected.")


if __name__ == "__main__":
    main()
