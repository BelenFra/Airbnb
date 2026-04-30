# Block 2 — Neighborhoods & Segments (K-Means)

**Question.** Within the top city (Hawaii — see Q1), which neighborhoods and listing segments offer the strongest risk-return profile?

## Method

- Clustering features (per listing): `log_price, occupancy_rate_proxy, accommodates, bedrooms, bathrooms, minimum_nights_capped`.
- Standardised, then `mba706_toolkit.perform_kmeans_clustering` (scipy `kmeans2`, k++ init, `RANDOM_STATE=42`).
- k chosen via `mba706_toolkit.perform_elbow_analysis`, capped at 6 for business explainability → final **k = 6**.
- Neighborhood ranking (Hawaii only): composite z-score = 0.5·revenue + 0.3·occupancy + 0.2·price (≥30 listings only).
- Supply-demand gap: per (city, cluster), classify by `median occupancy` vs `supply share` against the cross-city medians.

## k selection (silhouette + inertia)

|   k |   inertia |   silhouette |
|----:|----------:|-------------:|
|   2 |    423662 |       0.3336 |
|   3 |    334490 |       0.291  |
|   4 |    289076 |       0.2784 |
|   5 |    253378 |       0.2686 |
|   6 |    229136 |       0.2788 |
|   7 |    209532 |       0.2908 |
|   8 |    193621 |       0.2879 |

## Cluster profiles

|   cluster |   n_listings | median_price   | mean_price   | median_occupancy   | mean_occupancy   |   median_accommodates |   median_bedrooms |   median_bathrooms |   median_min_nights | est_annual_revenue_proxy   |   share_pct | top_room_type   | top_city    | cluster_name                 |
|----------:|-------------:|:---------------|:-------------|:-------------------|:-----------------|----------------------:|------------------:|-------------------:|--------------------:|:---------------------------|------------:|:----------------|:------------|:-----------------------------|
|         5 |        29095 | $125           | $161         | 10.7%              | 17.0%            |                     2 |                 1 |                1   |                  30 | $4,882                     |        28.3 | Entire home/apt | New York    | Long-stay focused            |
|         1 |        18242 | $136           | $165         | 76.2%              | 76.4%            |                     2 |                 1 |                1   |                   3 | $37,826                    |        17.7 | Entire home/apt | Los Angeles | Budget high-occupancy studio |
|         4 |        24473 | $153           | $179         | 16.4%              | 18.8%            |                     3 |                 1 |                1   |                   1 | $9,159                     |        23.8 | Entire home/apt | Hawaii      | General mid-tier             |
|         0 |        18379 | $312           | $463         | 34.8%              | 39.2%            |                     6 |                 2 |                2   |                   2 | $39,630                    |        17.9 | Entire home/apt | Hawaii      | Premium mid-size - active    |
|         2 |        10660 | $395           | $621         | 16.4%              | 24.0%            |                     8 |                 4 |                3   |                   3 | $23,645                    |        10.4 | Entire home/apt | Los Angeles | Premium mid-size - slow-turn |
|         3 |         2060 | $1,424         | $2,345       | 19.7%              | 26.2%            |                    12 |                 6 |                5.5 |                   3 | $102,393                   |         2   | Entire home/apt | Los Angeles | Luxury large home            |

## Top-10 Hawaii neighborhoods (composite score)

| neighbourhood_cleansed   |   rank |   n_listings | median_price   | median_occupancy   | median_revenue   | p75_revenue   |   z_median_revenue |   z_median_occupancy |   z_median_price |   premium_gap |   composite_score |
|:-------------------------|-------:|-------------:|:---------------|:-------------------|:-----------------|:--------------|-------------------:|---------------------:|-----------------:|--------------:|------------------:|
| Ewa                      |      1 |          827 | $461           | 47.7%              | $62,092          | $121,526      |              2.696 |                2.654 |            2.696 |         0.042 |             2.683 |
| Koloa-Poipu              |      2 |         1650 | $383           | 35.2%              | $50,601          | $96,503       |              1.893 |                1.082 |            1.788 |         0.706 |             1.629 |
| Lihue                    |      3 |          759 | $286           | 37.3%              | $47,128          | $80,942       |              1.651 |                1.341 |            0.658 |        -0.683 |             1.359 |
| Lahaina                  |      4 |         5147 | $367           | 31.8%              | $40,866          | $116,407      |              1.213 |                0.65  |            1.602 |         0.952 |             1.122 |
| South Kohala             |      5 |         1941 | $318           | 29.3%              | $38,225          | $68,614       |              1.029 |                0.339 |            1.031 |         0.692 |             0.822 |
| Kapaa-Wailua             |      6 |          829 | $249           | 32.6%              | $34,060          | $59,898       |              0.738 |                0.753 |            0.228 |        -0.525 |             0.64  |
| North Shore Kauai        |      7 |         2307 | $278           | 30.7%              | $34,113          | $63,938       |              0.742 |                0.512 |            0.565 |         0.053 |             0.638 |
| Koolauloa                |      8 |          581 | $300           | 28.5%              | $30,318          | $57,933       |              0.477 |                0.235 |            0.821 |         0.586 |             0.473 |
| North Kona               |      9 |         3609 | $200           | 34.2%              | $27,384          | $54,051       |              0.272 |                0.961 |           -0.343 |        -1.304 |             0.356 |
| Koolaupoko               |     10 |          409 | $262           | 29.9%              | $24,975          | $48,117       |              0.103 |                0.408 |            0.379 |        -0.029 |             0.25  |

> **`premium_gap` reading:** positive = neighborhood is priced above the city average more than its occupancy supports → over-priced; negative = under-priced relative to demand → potential pricing power.

## Supply-demand status (per city × segment)

| City          |   cluster |   n_listings | median_occupancy   | supply_share_in_city   | status                      |
|:--------------|----------:|-------------:|:-------------------|:-----------------------|:----------------------------|
| Hawaii        |         1 |         5067 | 77.3%              | 15.5%                  | Hot & crowded — competitive |
| Hawaii        |         3 |          684 | 37.3%              | 2.1%                   | Underserved — opportunity   |
| Hawaii        |         0 |        10699 | 34.2%              | 32.7%                  | Hot & crowded — competitive |
| Hawaii        |         2 |         2685 | 26.0%              | 8.2%                   | Underserved — opportunity   |
| Hawaii        |         5 |         2001 | 20.8%              | 6.1%                   | Underserved — opportunity   |
| Hawaii        |         4 |        11533 | 20.3%              | 35.3%                  | Oversupplied — risk         |
| Los Angeles   |         1 |         6324 | 76.2%              | 17.2%                  | Hot & crowded — competitive |
| Los Angeles   |         0 |         4810 | 37.5%              | 13.1%                  | Hot & crowded — competitive |
| Los Angeles   |         2 |         4778 | 11.0%              | 13.0%                  | Cold & thin — niche         |
| Los Angeles   |         4 |         7747 | 9.6%               | 21.1%                  | Oversupplied — risk         |
| Los Angeles   |         5 |        12002 | 7.9%               | 32.7%                  | Oversupplied — risk         |
| Los Angeles   |         3 |         1061 | 5.2%               | 2.9%                   | Cold & thin — niche         |
| Nashville     |         1 |          831 | 73.7%              | 12.5%                  | Underserved — opportunity   |
| Nashville     |         0 |         1225 | 26.3%              | 18.5%                  | Hot & crowded — competitive |
| Nashville     |         3 |          234 | 14.5%              | 3.5%                   | Cold & thin — niche         |
| Nashville     |         5 |          557 | 14.0%              | 8.4%                   | Cold & thin — niche         |
| Nashville     |         2 |         2081 | 11.2%              | 31.4%                  | Oversupplied — risk         |
| Nashville     |         4 |         1702 | 9.6%               | 25.7%                  | Oversupplied — risk         |
| New York      |         1 |         4531 | 75.6%              | 21.5%                  | Hot & crowded — competitive |
| New York      |         0 |          965 | 42.5%              | 4.6%                   | Underserved — opportunity   |
| New York      |         3 |           53 | 20.8%              | 0.3%                   | Underserved — opportunity   |
| New York      |         4 |         1959 | 17.8%              | 9.3%                   | Cold & thin — niche         |
| New York      |         2 |          831 | 11.5%              | 3.9%                   | Cold & thin — niche         |
| New York      |         5 |        12771 | 11.2%              | 60.5%                  | Oversupplied — risk         |
| San Francisco |         1 |         1489 | 78.1%              | 25.8%                  | Hot & crowded — competitive |
| San Francisco |         0 |          680 | 44.8%              | 11.8%                  | Underserved — opportunity   |
| San Francisco |         3 |           28 | 29.3%              | 0.5%                   | Underserved — opportunity   |
| San Francisco |         2 |          285 | 21.1%              | 4.9%                   | Underserved — opportunity   |
| San Francisco |         5 |         1764 | 20.8%              | 30.5%                  | Hot & crowded — competitive |
| San Francisco |         4 |         1532 | 14.7%              | 26.5%                  | Oversupplied — risk         |

## Figures

- `reports/figures/02_segmentation/01_elbow_silhouette.png`
- `reports/figures/02_segmentation/02_cluster_scatter_price_occupancy.png`
- `reports/figures/02_segmentation/03_cluster_profile_heatmap.png`
- `reports/figures/02_segmentation/04_neighborhood_ranking_hawaii.png`
- `reports/figures/02_segmentation/05_supply_demand_gap.png`

## Hand-off to Block 5 (Investment Decision)

- Recommended **segments to short-list**: `Luxury large home` (cluster 3), `Premium mid-size - active` (cluster 0).
- Recommended **Hawaii neighborhoods to short-list**: `Ewa`, `Koloa-Poipu`, `Lihue`.
- Use `cluster_assignments.csv` as the join key for Block 5 (`listing_id, City, cluster, cluster_name`).
