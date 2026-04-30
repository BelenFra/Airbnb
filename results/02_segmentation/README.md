# `results/02_segmentation/` — Neighborhood and Segment Questions

Outputs that answer the **Neighborhood and Segment Questions** in the TP brief:

- Which neighborhoods within the top city offer the best revenue potential?
- Are there distinct listing segments (budget studio, luxury beachfront,
  family suburban …) with different revenue profiles?
- Which segments are oversaturated and which are underserved?
- Do certain neighborhoods command a price premium that is not justified
  by their occupancy rates, or vice versa?

## Suggested artefacts

| File | Produced by | Describes |
| --- | --- | --- |
| `cluster_profiles.csv` | k-means script | One row per cluster: name, size, mean ADR, mean occupancy, top neighborhoods, modal property type. |
| `neighborhood_rankings.csv` | TBD | Per-city neighborhood scoring on revenue, supply density, premium gap. |
| `segment_supply_demand_gap.csv` | TBD | Segment × city → listings count, demand index, gap classification. |
| `cluster_silhouette.csv` | k-means script | k vs silhouette / elbow values for the chosen `k` justification. |

## Conventions

- Cluster IDs are integer; cluster *names* are short business-friendly
  labels added in a `cluster_label` column (e.g. `"luxury beachfront"`).
- Segment definitions (room type × bedrooms × price band) are documented
  in the script that produces the file.
- The chosen `k` for the final clustering is justified in `cluster_silhouette.csv`
  + a short paragraph in the memo.
