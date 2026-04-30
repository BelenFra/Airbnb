# Pricing Optimization / Elasticity Sub-Block — Descriptive Memo

**Audience:** Investment / strategy team  
**Status:** Internal descriptive pass (no causal elasticity estimated)  
**Relationship to other work:** This sub-block is **separate** from the completed Property / Pricing (nightly price) model. It uses the same upstream `master_data.csv` integrations but **does not** reuse or retrain that model here.

---

## 1. Business question

Before investing in downstream **pricing optimization** or **elasticity** work, how do **posted nightly price**, **estimated annual occupancy**, and **annual revenue (proxy)** hang together across listings—overall, by city, by room type, and across simple price bands? In plain terms: 

- Does the **top end of the price distribution** actually show higher **estimated annual revenue** in the cross-section?  
- Is there visible **tension** between higher prices and fewer **estimated occupied nights**?  
- Does the **picture change** materially by metro or listing product type?

---

## 2. Data and measures

| Element | Definition |
|--------|-------------|
| **Source** | `master_data.csv` (read-only; one row excluded for invalid price; see reproducible outputs). |
| **Working sample size** | **103,707** listings. |
| **Price** | Nightly advertised price (USD), strictly positive after filters. |
| **Occupancy** | `estimated_occupancy_l365d` — Inside-Airbnb-style **estimated** occupied nights over the trailing year (chosen as the principal occupancy construct for this sub-block). |
| **Annual revenue proxy** | `annual_revenue_proxy = price × estimated_occupancy_l365d`. **Not** audited realized revenue — it mechanically reflects **estimated** nights and headline price only. |

**Price bands:** “Low / Mid / High” are **equal listing-count tertiles** of nightly price on the working sample (not equal dollar-width buckets). Cutpoints are **P33 ≈ $132**, **P66 ≈ $250** per the generated tables. Within-city and within-room-type bands use the same tertile logic with market-specific cutpoints.

---

## 3. Key descriptive findings

**Overall averages (working sample)**  
Approximate sample means: nightly price ~**$599**, estimated occupancy ~**72** nights, annual revenue proxy ~**$16,587** — with substantial spread (distribution detail in appendix tables).

**Associations (Pearson, same sample)**  
- **Price ↔ estimated occupancy:** weak linear negative (**≈ −0.09**); **log(price) ↔ occupancy** about **−0.16**.  
- **Price ↔ revenue proxy:** weak positive (**≈ 0.19**); occupancy and revenue proxy share the same upward correlation with each other (**≈ 0.19**) because proxy revenue is mechanically `price × nights`.

**Global price tertiles — mean nightly price vs mean estimated occupancy vs mean proxy revenue**

| Band (equal count) | ~Listings | ~Mean nightly price | ~Mean est. occupancy (nights) | ~Mean annual revenue proxy |
|--------------------|-----------|---------------------|-------------------------------|-----------------------------|
| Low | 34,650 | $86 | 84 | $7,703 |
| Mid | 34,844 | $184 | 83 | $15,011 |
| High | 34,213 | $1,540 | 51 | **$27,189** |

The High band has a **very high average nightly price** because it contains **everything above ~$250** per night, including a long right tail of luxury outliers—while still representing only one-third of rows by construction.

---

## 4. What this suggests (associational narrative only)

Taken together as **patterns among different listings** (not as proof of “if we change price…”):

1. **Revenue proxy rises on average toward the expensive tertile.** In this snapshot, the **upper global price third** carries the highest **mean annual revenue proxy** versus Mid and Low, with Mid between Low and High. That is consistent with price levels and thick tails outweighing fewer estimated nights in the aggregate mean—**without** implying that repricing causes that outcome.

2. **Higher prices sit with fewer estimated occupied nights descriptively.** Band means and correlations both point toward a cross-sectional **tradeoff shape**: upscale listings estimate fewer annual nights yet can still dominate **average** proxy revenue when nightly price is extreme.

3. **Heterogeneity by city and room type.** City-level means (counts, mean price, occupancy, proxy revenue) and room-type summaries differ materially; within-city tertile tables show how local “who wins which band” can vary **even though** aggregate shortcuts (e.g. common “winner” bands in the automated summary) summarize many metros at once.

4. **`annual_revenue_proxy` aligns with supplied revenue logic.** On this sample the proxy reconciles numerically with `estimated_revenue_l365d` in the upstream file—a useful coherence check before any causal machinery.

---

## 5. Caution — not causal elasticity

These results describe **who is where** in the joint distribution (selection, quality, positioning, scraping estimates, tails). **They are not:**

- Estimated **elasticity** of demand with respect to price,  
- A **controlled** effect of “raising price holding all else fixed,”  
- Or **validated** causal evidence for underwriting an acquisition or renovation strategy.

Proper elasticity / optimization modeling requires explicit design (instruments, causal panels, experimentation, structural assumptions, etc.). That step is intentionally **not** claimed here.

---

## 6. Contribution to the final investment recommendation

| Contribution | Role in the storyline |
|--------------|------------------------|
| **Ground truth on definitions** | Team agrees occupancy for this tract is **`estimated_occupancy_l365d`** and revenue talk uses a **labeled proxy**, not audited P&L. |
| **Scope for optimization** | Descriptive coexistence of **high price**, **lower estimated nights**, but **often higher proxy revenue at the mean in top tertiles** frames where **scenario analysis** later adds value—without prematurely claiming win-win from simple repricing. |
| **Stratification** | City and room-type dispersion argues for **localized** elasticity and benchmarking—not one global recommendation. |
| **Risk framing** | Right-tail prices and scraped estimates underscore **confidence bands** and **quality review** before any mandate from this sub-block. |

**Bottom line:** This sub-block establishes a **transparent, repeatable descriptive baseline** linking price, estimated occupancy, and revenue proxy—the table stakes for credible **pricing optimization / elasticity** work to follow—not a substitute for that work.

---

*Evidence tables referenced from `pricing_optimization_descriptive/outputs/tables/`; reproducible driver: `pricing_optimization_descriptive/run_descriptive_analysis.py`.*
