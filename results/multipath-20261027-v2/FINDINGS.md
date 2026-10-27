# Fractional multipath routing: matched later-period comparison

Every declared method is reported. The protocol, original model hashes, verified input hashes and scientific source hashes were frozen locally before routing outcomes. This is not an external preregistration. No neural model was retrained; GNN and persistence use the original checkpoints and original validation margins.

## Source-availability preflight

The first proposed GÉANT period (22–28 July) failed the native-source availability rule with 132 empty demand sections. No routing results were produced for that attempt. The first consecutive seven-day period on/after 22 July with nonempty demand sections and a complete initial three-hour lookback starts on 26 July; it was selected using availability only. The failed protocol and screen are retained in ../multipath-20261027/. A nonempty source section does not prove complete or accurate traffic; individual unlisted OD demands still follow the original zero rule.

## Method and comparison contract

The LP conserves 100% of each predicted OD aggregate over the same delay-bounded candidate paths. It minimizes maximum link utilization for the per-OD maximum over three forecast horizons. Carbon mode then minimizes offered-traffic-weighted path carbon with peak utilization limited to max(0.8, the minimum achievable envelope peak). TE mode retains the minimum peak and has no carbon objective. Thus the TE/carbon comparison includes an explicit 80% planning-headroom tradeoff, not a promise of simultaneous minimum carbon and minimum utilization. A final LP minimizes L1 changes in path fractions. The quantized variant rounds to 100 buckets per OD and reports post-rounding planning-guard violations.

Actual current demand is revealed only after fractions are committed. The same equal-rate max-min allocator serves whole OD aggregates using fractional link incidence; subpaths never earn extra fairness shares. One-hot routing matches the original single-path allocator and is checked during replay. Offered utilization includes ALL offered bytes, including traffic that cannot be served; the optimizer cannot invent savings by admitting less traffic before overload accounting.

This is an ideal aggregate fractional model. It does not demonstrate switch configuration, flow hashing, packet ordering, TCP goodput or measured packet latency. The rounded variant tests finite weights only; it does not prove practical flow-level realizability. Paths may share bottlenecks, and no split can increase those physical cut capacities.

GÉANT pairs 2005 traffic with 2022 daily country carbon. Abilene uses fixed 2004 annual EPA regional rates. Carbon scores and carbon-weighted bytes are forwarding attribution proxies, not measured emissions. Selected flows, fixed assumed capacities, training-only traffic scaling, one existing model seed and seven adjacent days limit the conclusions.

## Metrics

Service pools served bytes / offered bytes across seven days. Carbon score, worst-pair service, overload minutes, active paths, changed OD aggregates and solver time are arithmetic daily means. A changed pair counts once even when several path weights change; redistributed mass is half the L1 weight change summed over pairs and intervals. Many tiny LP changes can increase changed-pair counts, so read them alongside redistributed mass. Undefined carbon days are counted explicitly. Absolute carbon-weighted bytes and served bytes remain in summary.csv so score reductions can be assessed alongside service and traffic mix.

## GEANT

Replay days: 2005-07-26, 2005-07-27, 2005-07-28, 2005-07-29, 2005-07-30, 2005-07-31, 2005-08-01.

### Normal

| Policy | Carbon score ↓ | Score days | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day | Redistributed mass/day | Paths/pair | Decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 732.43 | 7/7 | 42.898 | 52.337 | 769.29 | 0.00 | 0.000 | 1.00 | 0.04 |
| reactive_carbon | 596.24 | 7/7 | 50.581 | 59.389 | 675.00 | 19.57 | 19.571 | 1.00 | 0.25 |
| tradeoff_gnn | 556.96 | 7/7 | 50.529 | 59.338 | 677.14 | 24.43 | 24.429 | 1.00 | 1.18 |
| service_first_gnn | 552.67 | 7/7 | 50.433 | 59.151 | 690.00 | 26.43 | 26.429 | 1.00 | 2.03 |
| service_first_persistence | 553.79 | 7/7 | 50.493 | 59.572 | 675.00 | 25.57 | 25.571 | 1.00 | 1.51 |
| equal_split | 612.90 | 7/7 | 61.819 | 69.834 | 497.14 | 6.00 | 3.000 | 2.00 | 0.00 |
| multipath_te_gnn | 612.11 | 7/7 | 60.180 | 68.431 | 510.00 | 100.43 | 3.676 | 1.41 | 3.83 |
| multipath_carbon_gnn | 571.10 | 7/7 | 56.961 | 65.549 | 546.43 | 78.71 | 13.915 | 1.17 | 5.15 |
| multipath_carbon_persistence | 570.48 | 7/7 | 57.354 | 65.944 | 537.86 | 81.43 | 14.453 | 1.18 | 4.26 |
| multipath_carbon_reactive | 566.40 | 7/7 | 57.116 | 65.348 | 565.71 | 80.43 | 14.307 | 1.24 | 4.47 |
| multipath_carbon_gnn_quantized | 571.07 | 7/7 | 56.965 | 65.549 | 546.43 | 68.00 | 13.901 | 1.11 | 5.38 |

Quantized planning-guard violations: 370 out of 672 replay bins. These are forecast-envelope checks, not actual overload counts.

### Congested

| Policy | Carbon score ↓ | Score days | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day | Redistributed mass/day | Paths/pair | Decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 745.79 | 7/7 | 32.459 | 40.621 | 972.86 | 0.00 | 0.000 | 1.00 | 0.04 |
| reactive_carbon | 637.64 | 7/7 | 41.308 | 48.265 | 848.57 | 29.86 | 29.857 | 1.00 | 0.25 |
| tradeoff_gnn | 595.81 | 7/7 | 41.304 | 48.234 | 850.71 | 30.00 | 30.000 | 1.00 | 1.11 |
| service_first_gnn | 593.50 | 7/7 | 41.091 | 48.389 | 885.00 | 26.00 | 26.000 | 1.00 | 2.08 |
| service_first_persistence | 595.30 | 7/7 | 41.272 | 48.181 | 857.14 | 27.14 | 27.143 | 1.00 | 1.61 |
| equal_split | 651.04 | 7/7 | 47.668 | 56.210 | 707.14 | 6.00 | 3.000 | 2.00 | 0.00 |
| multipath_te_gnn | 651.18 | 7/7 | 45.236 | 54.060 | 741.43 | 100.86 | 4.273 | 1.41 | 3.83 |
| multipath_carbon_gnn | 620.57 | 7/7 | 41.804 | 50.854 | 795.00 | 89.43 | 14.175 | 1.20 | 5.07 |
| multipath_carbon_persistence | 620.03 | 7/7 | 42.042 | 51.100 | 777.86 | 95.29 | 14.609 | 1.22 | 4.31 |
| multipath_carbon_reactive | 616.51 | 7/7 | 41.864 | 50.983 | 801.43 | 93.57 | 14.859 | 1.27 | 4.18 |
| multipath_carbon_gnn_quantized | 620.58 | 7/7 | 41.827 | 50.848 | 797.14 | 78.57 | 14.167 | 1.13 | 5.22 |

Quantized planning-guard violations: 466 out of 672 replay bins. These are forecast-envelope checks, not actual overload counts.

### Bursty

| Policy | Carbon score ↓ | Score days | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day | Redistributed mass/day | Paths/pair | Decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 736.94 | 7/7 | 35.273 | 43.135 | 837.86 | 0.00 | 0.000 | 1.00 | 0.04 |
| reactive_carbon | 618.04 | 7/7 | 43.918 | 49.683 | 765.00 | 27.00 | 27.000 | 1.00 | 0.23 |
| tradeoff_gnn | 580.74 | 7/7 | 43.963 | 49.677 | 765.00 | 35.14 | 35.143 | 1.00 | 1.13 |
| service_first_gnn | 576.28 | 7/7 | 43.815 | 49.633 | 784.29 | 34.71 | 34.714 | 1.00 | 2.26 |
| service_first_persistence | 578.50 | 7/7 | 43.923 | 49.811 | 767.14 | 37.14 | 37.143 | 1.00 | 1.55 |
| equal_split | 637.14 | 7/7 | 51.830 | 59.015 | 615.00 | 6.00 | 3.000 | 2.00 | 0.00 |
| multipath_te_gnn | 630.48 | 7/7 | 50.107 | 56.897 | 642.86 | 99.00 | 4.930 | 1.41 | 3.79 |
| multipath_carbon_gnn | 593.36 | 7/7 | 46.232 | 53.389 | 709.29 | 88.00 | 17.470 | 1.19 | 5.11 |
| multipath_carbon_persistence | 593.42 | 7/7 | 46.480 | 53.625 | 698.57 | 91.00 | 18.203 | 1.20 | 4.29 |
| multipath_carbon_reactive | 589.88 | 7/7 | 46.218 | 53.097 | 720.00 | 88.57 | 17.521 | 1.26 | 4.19 |
| multipath_carbon_gnn_quantized | 593.30 | 7/7 | 46.235 | 53.399 | 709.29 | 79.71 | 17.467 | 1.12 | 5.18 |

Quantized planning-guard violations: 411 out of 672 replay bins. These are forecast-envelope checks, not actual overload counts.

## ABILENE

Replay days: 2004-05-24, 2004-05-25, 2004-05-26, 2004-05-27, 2004-05-28, 2004-05-29, 2004-05-30.

### Normal

| Policy | Carbon score ↓ | Score days | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day | Redistributed mass/day | Paths/pair | Decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2138.04 | 7/7 | 97.233 | 93.851 | 30.71 | 0.00 | 0.000 | 1.00 | 0.04 |
| reactive_carbon | 1888.66 | 7/7 | 97.639 | 95.307 | 27.86 | 4.86 | 4.857 | 1.00 | 0.31 |
| tradeoff_gnn | 1884.66 | 7/7 | 97.639 | 95.307 | 27.86 | 5.71 | 5.714 | 1.00 | 2.23 |
| service_first_gnn | 1880.78 | 7/7 | 97.547 | 94.994 | 28.57 | 6.29 | 6.286 | 1.00 | 5.29 |
| service_first_persistence | 1880.73 | 7/7 | 97.562 | 95.038 | 28.57 | 6.29 | 6.286 | 1.00 | 5.19 |
| equal_split | 2444.97 | 7/7 | 97.295 | 94.632 | 27.86 | 6.00 | 3.667 | 2.67 | 0.00 |
| multipath_te_gnn | 2068.59 | 7/7 | 98.254 | 97.326 | 20.71 | 266.71 | 12.891 | 1.56 | 5.34 |
| multipath_carbon_gnn | 1887.72 | 7/7 | 97.947 | 96.384 | 25.00 | 19.29 | 7.549 | 1.17 | 5.97 |
| multipath_carbon_persistence | 1887.76 | 7/7 | 97.949 | 96.390 | 25.00 | 19.29 | 7.533 | 1.17 | 4.66 |
| multipath_carbon_reactive | 1888.02 | 7/7 | 97.915 | 96.284 | 25.71 | 19.00 | 7.600 | 1.17 | 4.55 |
| multipath_carbon_gnn_quantized | 1887.72 | 7/7 | 97.944 | 96.376 | 25.00 | 17.57 | 7.546 | 1.01 | 5.97 |

Quantized planning-guard violations: 55 out of 2016 replay bins. These are forecast-envelope checks, not actual overload counts.

### Congested

| Policy | Carbon score ↓ | Score days | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day | Redistributed mass/day | Paths/pair | Decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2156.06 | 7/7 | 95.736 | 88.692 | 56.43 | 0.00 | 0.000 | 1.00 | 0.04 |
| reactive_carbon | 1926.00 | 7/7 | 96.508 | 91.490 | 49.29 | 16.43 | 16.429 | 1.00 | 0.31 |
| tradeoff_gnn | 1915.32 | 7/7 | 96.508 | 91.490 | 49.29 | 23.29 | 23.286 | 1.00 | 2.24 |
| service_first_gnn | 1896.05 | 7/7 | 96.486 | 91.472 | 52.14 | 13.71 | 13.714 | 1.00 | 5.76 |
| service_first_persistence | 1896.06 | 7/7 | 96.486 | 91.472 | 52.14 | 14.00 | 14.000 | 1.00 | 5.47 |
| equal_split | 2463.19 | 7/7 | 92.279 | 84.714 | 357.14 | 6.00 | 3.667 | 2.67 | 0.00 |
| multipath_te_gnn | 2084.03 | 7/7 | 96.613 | 92.035 | 43.57 | 265.71 | 13.068 | 1.53 | 4.48 |
| multipath_carbon_gnn | 1910.36 | 7/7 | 95.942 | 89.925 | 48.57 | 175.71 | 22.103 | 1.19 | 6.05 |
| multipath_carbon_persistence | 1910.45 | 7/7 | 95.942 | 89.927 | 48.57 | 175.14 | 22.113 | 1.19 | 4.64 |
| multipath_carbon_reactive | 1909.62 | 7/7 | 95.879 | 89.739 | 49.29 | 144.57 | 19.862 | 1.19 | 4.56 |
| multipath_carbon_gnn_quantized | 1910.36 | 7/7 | 95.943 | 89.928 | 48.57 | 129.71 | 22.109 | 1.06 | 5.90 |

Quantized planning-guard violations: 395 out of 2016 replay bins. These are forecast-envelope checks, not actual overload counts.

### Bursty

| Policy | Carbon score ↓ | Score days | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day | Redistributed mass/day | Paths/pair | Decision ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2147.92 | 7/7 | 95.429 | 89.345 | 78.57 | 0.00 | 0.000 | 1.00 | 0.04 |
| reactive_carbon | 1938.11 | 7/7 | 95.666 | 90.140 | 77.86 | 37.14 | 37.143 | 1.00 | 0.31 |
| tradeoff_gnn | 1918.45 | 7/7 | 95.879 | 90.683 | 77.14 | 47.57 | 47.571 | 1.00 | 2.06 |
| service_first_gnn | 1900.53 | 7/7 | 95.796 | 90.632 | 86.43 | 30.00 | 30.000 | 1.00 | 5.13 |
| service_first_persistence | 1900.83 | 7/7 | 95.796 | 90.632 | 86.43 | 30.00 | 30.000 | 1.00 | 4.77 |
| equal_split | 2448.54 | 7/7 | 93.099 | 86.788 | 173.57 | 6.00 | 3.667 | 2.67 | 0.00 |
| multipath_te_gnn | 2072.32 | 7/7 | 96.502 | 92.009 | 46.43 | 350.57 | 40.214 | 1.57 | 4.53 |
| multipath_carbon_gnn | 1905.27 | 7/7 | 95.821 | 90.583 | 72.86 | 162.71 | 41.844 | 1.20 | 5.96 |
| multipath_carbon_persistence | 1905.35 | 7/7 | 95.823 | 90.587 | 72.86 | 163.57 | 41.902 | 1.20 | 4.74 |
| multipath_carbon_reactive | 1904.17 | 7/7 | 95.777 | 90.504 | 74.29 | 130.43 | 37.169 | 1.19 | 4.88 |
| multipath_carbon_gnn_quantized | 1905.24 | 7/7 | 95.823 | 90.593 | 72.86 | 125.29 | 41.843 | 1.04 | 6.63 |

Quantized planning-guard violations: 270 out of 2016 replay bins. These are forecast-envelope checks, not actual overload counts.

## Uncertainty and interpretation

Paired daily differences and descriptive day-bootstrap intervals are saved. Carbon intervals use only days with defined paired scores. Served-fraction intervals concern the arithmetic mean of daily fractions, not the pooled-byte percentage above. Few adjacent days, one training seed and multiple comparisons do not establish broad statistical generalization. Compare against the matched no-carbon and persistence methods before attributing any gain to the carbon objective or GNN. All previous evaluated periods remain inspected; changes informed by this study require another protocol and new evaluation, not silent replacement of these results.
