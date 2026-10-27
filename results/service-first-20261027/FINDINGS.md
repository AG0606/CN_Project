# Service-first routing: later-period evaluation

The protocol and scientific source hashes were frozen locally before routing outcomes. This is not an external preregistration. Every declared policy is reported, using the same historical demand, carbon, candidate paths, assumed capacities and one-bin observation delay.

Service-first enumerates single-path assignments and applies the same max-min rate allocator to the forecast for each horizon. Assignments within 0.1% of total predicted offered demand of the best predicted served amount are eligible; among them the planner minimizes predicted served-byte carbon score, breaking ties by route changes and delay. The selected assignment is committed before current demand is revealed. This is a fixed design choice, not a guarantee about actual service or carbon.

The GNN and persistence variants use the original trained checkpoints and their original validation margins; no new model training was performed. Carbon is a forwarding attribution proxy, not grams of measured CO₂. GÉANT traffic (2005) is paired with 2022 daily country intensities; Abilene uses 2004 annual regional rates. Assumed capacities, selected OD pairs, workload scaling, and the aggregate service model limit real-world interpretation.

GÉANT's declared source-availability rule requires nonempty native demand sections for each replay bin and its initial lookback. A nonempty section does not establish complete or accurate traffic, and unlisted individual OD pairs remain zero under the original parser. The oracle sees current demand and is diagnostic only; it is not a bound on the reported score.

Pooled service is total served MB divided by total offered MB. Worst-pair service is the daily minimum served/offered among active pairs, averaged over days. Carbon score, overload, changes, decision time and modeled path delay are arithmetic daily means; path delay is a propagation/router proxy, not measured packet latency. Read all metrics together.

## GEANT

Replay days: 2005-07-14, 2005-07-15, 2005-07-16, 2005-07-17, 2005-07-18, 2005-07-19, 2005-07-20.

### Normal workload

| Policy | Carbon score ↓ | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changes/day ↓ | Decision ms | Path delay ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 523.68 | 25.85 | 23.07 | 1225.71 | 0.00 | 0.04 | 4.95 |
| reactive_carbon | 425.18 | 26.52 | 25.30 | 1202.14 | 12.71 | 0.23 | 5.44 |
| predictive_te | 394.19 | 26.56 | 25.38 | 1197.86 | 2.57 | 0.90 | 5.54 |
| tradeoff_gnn | 331.37 | 26.51 | 25.30 | 1202.14 | 16.29 | 1.11 | 5.75 |
| tradeoff_persistence | 331.29 | 26.51 | 25.30 | 1202.14 | 15.71 | 0.42 | 5.75 |
| service_first_gnn | 330.60 | 26.46 | 25.09 | 1204.29 | 18.86 | 2.22 | 5.73 |
| service_first_persistence | 330.55 | 26.46 | 25.09 | 1204.29 | 20.86 | 1.60 | 5.73 |
| oracle_current_bin | 329.49 | 26.57 | 25.39 | 1195.71 | 17.14 | 0.10 | 5.75 |

### Congested workload

| Policy | Carbon score ↓ | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changes/day ↓ | Decision ms | Path delay ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 543.24 | 19.13 | 14.39 | 1290.00 | 0.00 | 0.03 | 4.84 |
| reactive_carbon | 454.20 | 19.69 | 16.66 | 1275.00 | 15.14 | 0.23 | 5.32 |
| predictive_te | 432.19 | 19.71 | 16.71 | 1275.00 | 3.29 | 0.84 | 5.44 |
| tradeoff_gnn | 371.92 | 19.60 | 16.64 | 1277.14 | 18.29 | 1.12 | 5.62 |
| tradeoff_persistence | 372.08 | 19.61 | 16.66 | 1275.00 | 18.57 | 0.43 | 5.62 |
| service_first_gnn | 369.59 | 19.67 | 16.66 | 1281.43 | 18.14 | 2.23 | 5.56 |
| service_first_persistence | 370.09 | 19.68 | 16.68 | 1279.29 | 17.86 | 1.57 | 5.55 |
| oracle_current_bin | 370.36 | 19.64 | 16.71 | 1275.00 | 16.86 | 0.10 | 5.63 |

### Bursty workload

| Policy | Carbon score ↓ | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changes/day ↓ | Decision ms | Path delay ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 536.25 | 20.74 | 17.27 | 1266.43 | 0.00 | 0.04 | 4.88 |
| reactive_carbon | 436.98 | 21.33 | 19.32 | 1251.43 | 16.29 | 0.24 | 5.38 |
| predictive_te | 407.58 | 21.37 | 19.37 | 1249.29 | 5.29 | 0.87 | 5.51 |
| tradeoff_gnn | 353.60 | 21.31 | 19.32 | 1251.43 | 20.00 | 1.15 | 5.66 |
| tradeoff_persistence | 353.90 | 21.31 | 19.32 | 1251.43 | 21.71 | 0.42 | 5.66 |
| service_first_gnn | 353.95 | 21.30 | 19.22 | 1251.43 | 26.86 | 2.19 | 5.61 |
| service_first_persistence | 353.66 | 21.34 | 19.29 | 1251.43 | 27.71 | 1.58 | 5.61 |
| oracle_current_bin | 352.25 | 21.38 | 19.35 | 1247.14 | 23.43 | 0.10 | 5.65 |

## ABILENE

Replay days: 2004-05-16, 2004-05-17, 2004-05-18, 2004-05-19, 2004-05-20, 2004-05-21, 2004-05-22.

### Normal workload

| Policy | Carbon score ↓ | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changes/day ↓ | Decision ms | Path delay ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2087.76 | 99.97 | 99.87 | 1.43 | 0.00 | 0.04 | 20.63 |
| reactive_carbon | 1877.52 | 99.99 | 99.93 | 1.43 | 1.57 | 0.30 | 21.24 |
| predictive_te | 2148.02 | 99.99 | 99.93 | 1.43 | 9.00 | 0.96 | 20.92 |
| tradeoff_gnn | 1875.79 | 99.99 | 99.93 | 1.43 | 1.86 | 2.00 | 21.38 |
| tradeoff_persistence | 1875.84 | 99.99 | 99.93 | 1.43 | 1.86 | 0.84 | 21.37 |
| service_first_gnn | 1871.15 | 99.98 | 99.93 | 2.14 | 2.86 | 5.08 | 21.74 |
| service_first_persistence | 1871.15 | 99.98 | 99.93 | 2.14 | 2.86 | 4.79 | 21.74 |
| oracle_current_bin | 1871.12 | 99.99 | 99.96 | 0.71 | 2.86 | 0.25 | 21.74 |

### Congested workload

| Policy | Carbon score ↓ | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changes/day ↓ | Decision ms | Path delay ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2088.04 | 99.90 | 99.61 | 15.71 | 0.00 | 0.04 | 20.64 |
| reactive_carbon | 2014.53 | 99.75 | 99.40 | 57.86 | 27.14 | 0.29 | 21.46 |
| predictive_te | 2147.27 | 99.90 | 99.73 | 10.71 | 19.00 | 0.96 | 20.93 |
| tradeoff_gnn | 1971.31 | 99.88 | 99.67 | 22.86 | 52.29 | 1.94 | 21.21 |
| tradeoff_persistence | 1971.24 | 99.88 | 99.67 | 22.14 | 52.86 | 0.85 | 21.20 |
| service_first_gnn | 1898.73 | 99.87 | 99.60 | 36.43 | 53.86 | 4.78 | 21.50 |
| service_first_persistence | 1899.61 | 99.88 | 99.61 | 34.29 | 54.14 | 4.51 | 21.49 |
| oracle_current_bin | 1890.21 | 99.92 | 99.78 | 7.86 | 51.71 | 0.20 | 21.53 |

### Bursty workload

| Policy | Carbon score ↓ | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changes/day ↓ | Decision ms | Path delay ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2076.90 | 98.51 | 96.82 | 166.43 | 0.00 | 0.04 | 20.45 |
| reactive_carbon | 1972.22 | 98.31 | 96.50 | 194.29 | 88.29 | 0.35 | 21.53 |
| predictive_te | 2164.34 | 98.78 | 97.50 | 147.86 | 85.86 | 1.07 | 20.96 |
| tradeoff_gnn | 1941.48 | 98.51 | 96.78 | 167.86 | 114.29 | 2.12 | 21.35 |
| tradeoff_persistence | 1941.37 | 98.51 | 96.78 | 167.86 | 114.29 | 0.87 | 21.36 |
| service_first_gnn | 1907.80 | 98.35 | 96.43 | 182.14 | 75.29 | 5.17 | 21.42 |
| service_first_persistence | 1907.99 | 98.35 | 96.43 | 182.14 | 76.43 | 4.62 | 21.43 |
| oracle_current_bin | 1915.82 | 99.29 | 98.35 | 95.71 | 72.29 | 0.23 | 21.46 |

## Interpretation

Compare service-first with both the reactive baseline and the existing joint planner, including the persistence variants. Lower carbon score can coexist with poorer service or a different traffic mix; absolute carbon-weighted bytes and all raw per-day outcomes are retained in summary.csv. Intervals in day_cluster_intervals.csv are descriptive bootstraps of only seven adjacent days, with one model seed and multiple comparisons. They are not strong evidence of generalization.
