# Final validation before paper writing

Independent audit passed: 2,058 runs, 395,136 replay intervals, 12 new checkpoints, 378 explicitly future-aware diagnostics. See AUDIT.json.

Three training seeds (7, 42, 123), fixed capacity scenarios (10, 20, 40 Mbps/direction), and the same planners receiving actual next-three-bin demand as explicitly future-aware diagnostics. No winning seed or scenario is selected. The protocol and evaluation plan were frozen locally; this is not an external preregistration.

Training used only the original training/validation splits and their transforms. GÉANT uses its original 40-epoch/8-patience limit; Abilene uses 25 epochs/patience 6. The frozen protocol's narrative generalized 40/8 to both networks; PROTOCOL_ERRATUM.json documents this wording error. The code always used the correct original per-network settings, recorded in the evaluation plan and checkpoint metadata. Test data did not enter training or checkpoint selection.

Capacity scenarios are declared assumptions, not measured historical capacities or guaranteed light/moderate/heavy regimes. Normal, scaled-congested and seeded-burst traffic is identical between every method in a paired condition. Model seed 42 is used for the capacity comparison; all three seeds are evaluated for the two primary GNN/GRU planners at reference capacity. Forecasts are cached across comparisons, so final-validation decision times exclude bulk neural forecasting and are not end-to-end deployment latency.

Perfect-demand controls use the same algorithm and current carbon as causal controls, with the true next three demand matrices and zero margin. They are not deployable or guaranteed bounds on realized service/carbon. Zero-margin causal seed42 controls at 10 Mbps isolate forecast replacement from margin removal; higher-capacity diagnostics also remove margins and should not be interpreted as an isolated forecast-accuracy effect.

All seven replay days are retained. Forecast metrics cover each replay-bin start, with two additional future-label bins beyond the last day; no gaps are crossed. Source availability is checked before outcomes. GÉANT uses daily 2022 country carbon with 2005 traffic; Abilene uses static annual 2004 EPA regional carbon. Scores are forwarding proxies, not measured CO₂.

## Check 1: forecast error across training seeds

Mean MAE across three horizons (Mbps), then mean/sample standard deviation across three training seeds. Persistence is deterministic and has no seed standard deviation. These standard deviations are not confidence intervals over independent test days.

| Network | GNN mean ± seed SD | GRU mean ± seed SD | Persistence |
| --- | ---: | ---: | ---: |
| geant | 1.99965 ± 0.02174 | 1.97566 ± 0.01296 | 1.97092 |
| abilene | 0.42134 ± 0.00523 | 0.41650 ± 0.00371 | 0.42746 |

## Check 2: matched routing/capacity outcomes

Service pools bytes. Carbon score, overload, worst-pair service and changes average daily runs. At reference capacity the GNN/GRU service-first and carbon-multipath rows average all three seeds; other capacities use seed42. Seed-specific rows remain in summary.csv. Reported seed counts exclude deterministic controls. Pooled percentages cannot be directly substituted for the arithmetic daily-fraction differences used in the uncertainty CSV.

### GEANT

Replay dates: 2005-08-03, 2005-08-04, 2005-08-05, 2005-08-06, 2005-08-07, 2005-08-08, 2005-08-09.

#### 10 Mbps / normal

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 651.81 | 26.133 | 20.173 | 966.43 | 0.00 |
| reactive_carbon | — | 463.28 | 33.660 | 27.300 | 919.29 | 16.29 |
| equal_split | — | 469.59 | 43.449 | 38.852 | 887.14 | 6.00 |
| service_first_persistence | — | 424.83 | 33.649 | 27.272 | 923.57 | 18.29 |
| multipath_carbon_persistence | — | 466.58 | 37.998 | 33.147 | 915.00 | 91.71 |
| service_first_gnn | 3 | 424.80 | 33.618 | 27.178 | 927.86 | 15.43 |
| service_first_gru | 3 | 424.35 | 33.581 | 27.151 | 930.71 | 15.05 |
| multipath_te_gnn | 1 | 485.76 | 40.430 | 35.844 | 900.00 | 98.71 |
| multipath_carbon_gnn | 3 | 469.23 | 37.664 | 32.795 | 915.00 | 87.90 |
| multipath_carbon_gru | 3 | 468.76 | 37.638 | 32.751 | 917.86 | 85.52 |
| service_first_gnn_no_margin | 1 | 424.02 | 33.521 | 27.097 | 938.57 | 15.43 |
| multipath_carbon_gnn_no_margin | 1 | 466.74 | 37.682 | 32.794 | 921.43 | 88.29 |
| perfect_service_first | — | 424.68 | 33.720 | 27.393 | 915.00 | 14.43 |
| perfect_multipath_carbon | — | 467.97 | 38.357 | 33.639 | 895.71 | 103.43 |
| perfect_multipath_te | — | 482.33 | 40.950 | 36.572 | 887.14 | 89.00 |

#### 10 Mbps / congested

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 680.69 | 18.684 | 13.589 | 1170.00 | 0.00 |
| reactive_carbon | — | 487.85 | 26.500 | 19.824 | 990.00 | 16.29 |
| equal_split | — | 524.32 | 30.487 | 24.454 | 927.86 | 6.00 |
| service_first_persistence | — | 484.43 | 26.447 | 19.777 | 994.29 | 18.00 |
| multipath_carbon_persistence | — | 526.27 | 25.408 | 19.750 | 964.29 | 102.43 |
| service_first_gnn | 3 | 482.63 | 26.408 | 19.761 | 1015.71 | 19.24 |
| service_first_gru | 3 | 481.71 | 26.380 | 19.743 | 1027.86 | 19.05 |
| multipath_te_gnn | 1 | 543.78 | 27.709 | 22.034 | 940.71 | 98.00 |
| multipath_carbon_gnn | 3 | 528.02 | 25.254 | 19.596 | 970.71 | 100.90 |
| multipath_carbon_gru | 3 | 527.14 | 25.239 | 19.591 | 970.71 | 100.48 |
| service_first_gnn_no_margin | 1 | 479.85 | 26.328 | 19.698 | 1058.57 | 22.00 |
| multipath_carbon_gnn_no_margin | 1 | 523.66 | 25.217 | 19.595 | 1017.86 | 117.00 |
| perfect_service_first | — | 485.02 | 26.513 | 19.827 | 975.00 | 19.14 |
| perfect_multipath_carbon | — | 527.76 | 25.453 | 19.820 | 953.57 | 116.71 |
| perfect_multipath_te | — | 542.47 | 27.891 | 22.312 | 934.29 | 89.00 |

#### 10 Mbps / bursty

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 665.95 | 21.331 | 17.037 | 1122.86 | 0.00 |
| reactive_carbon | — | 469.71 | 28.627 | 23.738 | 1005.00 | 22.57 |
| equal_split | — | 498.89 | 35.274 | 31.111 | 897.86 | 6.00 |
| service_first_persistence | — | 457.34 | 28.605 | 23.661 | 1005.00 | 26.86 |
| multipath_carbon_persistence | — | 493.74 | 30.377 | 26.426 | 977.14 | 101.43 |
| service_first_gnn | 3 | 456.72 | 28.590 | 23.656 | 1009.29 | 23.90 |
| service_first_gru | 3 | 455.79 | 28.532 | 23.627 | 1016.43 | 25.14 |
| multipath_te_gnn | 1 | 511.90 | 32.764 | 28.935 | 921.43 | 99.57 |
| multipath_carbon_gnn | 3 | 495.54 | 30.171 | 26.242 | 985.71 | 98.57 |
| multipath_carbon_gru | 3 | 494.74 | 30.126 | 26.194 | 994.29 | 96.71 |
| service_first_gnn_no_margin | 1 | 454.85 | 28.440 | 23.515 | 1035.00 | 26.57 |
| multipath_carbon_gnn_no_margin | 1 | 491.68 | 30.036 | 26.111 | 1009.29 | 111.71 |
| perfect_service_first | — | 459.59 | 28.730 | 23.809 | 972.86 | 26.14 |
| perfect_multipath_carbon | — | 496.39 | 30.673 | 26.757 | 932.14 | 120.86 |
| perfect_multipath_te | — | 511.44 | 32.984 | 29.257 | 902.14 | 89.57 |

#### 20 Mbps / normal

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 585.36 | 43.598 | 39.197 | 887.14 | 0.00 |
| reactive_carbon | — | 462.07 | 50.595 | 46.591 | 867.86 | 14.86 |
| equal_split | — | 408.02 | 73.901 | 73.472 | 649.29 | 6.00 |
| service_first_persistence | — | 342.80 | 50.515 | 46.467 | 870.00 | 16.86 |
| multipath_carbon_persistence | — | 387.40 | 69.818 | 68.998 | 720.00 | 72.57 |
| service_first_gnn | 1 | 342.79 | 50.503 | 46.454 | 870.00 | 16.86 |
| service_first_gru | 1 | 342.79 | 50.503 | 46.454 | 870.00 | 16.86 |
| multipath_te_gnn | 1 | 413.50 | 72.029 | 71.405 | 681.43 | 98.71 |
| multipath_carbon_gnn | 1 | 389.03 | 69.485 | 68.673 | 722.14 | 72.29 |
| multipath_carbon_gru | 1 | 388.92 | 69.467 | 68.679 | 724.29 | 72.29 |
| perfect_service_first | — | 342.79 | 50.797 | 46.840 | 867.86 | 13.29 |
| perfect_multipath_carbon | — | 389.91 | 71.583 | 71.217 | 670.71 | 90.57 |
| perfect_multipath_te | — | 409.84 | 72.904 | 72.518 | 664.29 | 89.00 |

#### 20 Mbps / congested

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 631.81 | 30.640 | 24.781 | 927.86 | 0.00 |
| reactive_carbon | — | 459.40 | 37.983 | 32.198 | 904.29 | 13.71 |
| equal_split | — | 445.89 | 51.862 | 48.396 | 859.29 | 6.00 |
| service_first_persistence | — | 396.83 | 37.861 | 32.001 | 910.71 | 15.43 |
| multipath_carbon_persistence | — | 435.74 | 46.658 | 42.794 | 893.57 | 78.86 |
| service_first_gnn | 1 | 396.79 | 37.860 | 32.001 | 910.71 | 15.43 |
| service_first_gru | 1 | 396.79 | 37.860 | 32.001 | 910.71 | 15.43 |
| multipath_te_gnn | 1 | 456.01 | 49.259 | 45.760 | 874.29 | 98.00 |
| multipath_carbon_gnn | 1 | 437.48 | 46.380 | 42.502 | 895.71 | 76.29 |
| multipath_carbon_gru | 1 | 437.59 | 46.351 | 42.471 | 895.71 | 76.14 |
| perfect_service_first | — | 396.41 | 38.060 | 32.337 | 902.14 | 13.29 |
| perfect_multipath_carbon | — | 437.65 | 47.385 | 43.841 | 872.14 | 94.71 |
| perfect_multipath_te | — | 454.34 | 49.710 | 46.390 | 867.86 | 89.00 |

#### 20 Mbps / bursty

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 610.11 | 35.409 | 31.367 | 897.86 | 0.00 |
| reactive_carbon | — | 470.50 | 42.430 | 38.706 | 880.71 | 20.00 |
| equal_split | — | 433.46 | 59.396 | 58.321 | 730.71 | 6.00 |
| service_first_persistence | — | 377.59 | 42.362 | 38.637 | 882.86 | 19.14 |
| multipath_carbon_persistence | — | 414.45 | 54.584 | 53.168 | 795.00 | 79.14 |
| service_first_gnn | 1 | 377.32 | 42.350 | 38.623 | 882.86 | 17.43 |
| service_first_gru | 1 | 377.32 | 42.350 | 38.623 | 882.86 | 17.43 |
| multipath_te_gnn | 1 | 439.43 | 57.060 | 56.027 | 758.57 | 99.57 |
| multipath_carbon_gnn | 1 | 415.86 | 54.367 | 52.955 | 795.00 | 78.14 |
| multipath_carbon_gru | 1 | 415.80 | 54.348 | 52.949 | 797.14 | 78.00 |
| perfect_service_first | — | 377.76 | 42.596 | 38.979 | 876.43 | 14.71 |
| perfect_multipath_carbon | — | 416.59 | 55.988 | 54.647 | 754.29 | 100.86 |
| perfect_multipath_te | — | 436.95 | 57.747 | 56.857 | 750.00 | 89.57 |

#### 40 Mbps / normal

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 533.38 | 74.007 | 73.720 | 645.00 | 0.00 |
| reactive_carbon | — | 442.49 | 78.871 | 78.792 | 589.29 | 28.71 |
| equal_split | — | 386.64 | 97.437 | 98.416 | 62.14 | 6.00 |
| service_first_persistence | — | 281.30 | 78.491 | 78.379 | 606.43 | 34.43 |
| multipath_carbon_persistence | — | 335.25 | 95.278 | 96.051 | 203.57 | 76.43 |
| service_first_gnn | 1 | 281.26 | 78.455 | 78.285 | 608.57 | 34.29 |
| service_first_gru | 1 | 281.26 | 78.456 | 78.285 | 608.57 | 34.57 |
| multipath_te_gnn | 1 | 388.87 | 97.266 | 98.291 | 77.14 | 98.71 |
| multipath_carbon_gnn | 1 | 334.61 | 95.050 | 95.821 | 207.86 | 75.71 |
| multipath_carbon_gru | 1 | 334.69 | 95.058 | 95.826 | 207.86 | 76.14 |
| perfect_service_first | — | 282.28 | 79.245 | 79.224 | 580.71 | 14.00 |
| perfect_multipath_carbon | — | 349.55 | 97.209 | 98.253 | 79.29 | 87.43 |
| perfect_multipath_te | — | 386.29 | 97.385 | 98.382 | 68.57 | 89.00 |

#### 40 Mbps / congested

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 565.27 | 52.009 | 48.739 | 857.14 | 0.00 |
| reactive_carbon | — | 448.18 | 58.672 | 55.772 | 825.00 | 16.29 |
| equal_split | — | 396.27 | 84.611 | 85.569 | 471.43 | 6.00 |
| service_first_persistence | — | 320.44 | 58.507 | 55.563 | 827.14 | 21.43 |
| multipath_carbon_persistence | — | 370.66 | 80.665 | 81.292 | 587.14 | 73.86 |
| service_first_gnn | 1 | 320.39 | 58.453 | 55.501 | 829.29 | 22.57 |
| service_first_gru | 1 | 320.37 | 58.439 | 55.489 | 829.29 | 22.29 |
| multipath_te_gnn | 1 | 398.81 | 83.472 | 84.286 | 501.43 | 98.00 |
| multipath_carbon_gnn | 1 | 371.35 | 80.412 | 81.067 | 587.14 | 72.86 |
| multipath_carbon_gru | 1 | 371.51 | 80.388 | 81.034 | 591.43 | 73.00 |
| perfect_service_first | — | 320.73 | 58.887 | 56.024 | 818.57 | 12.43 |
| perfect_multipath_carbon | — | 376.03 | 83.153 | 84.171 | 492.86 | 90.57 |
| perfect_multipath_te | — | 396.82 | 84.064 | 85.047 | 486.43 | 89.00 |

#### 40 Mbps / bursty

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 554.59 | 59.508 | 58.602 | 724.29 | 0.00 |
| reactive_carbon | — | 462.24 | 65.021 | 64.769 | 668.57 | 25.00 |
| equal_split | — | 400.14 | 85.611 | 87.051 | 220.71 | 6.00 |
| service_first_persistence | — | 308.42 | 64.777 | 64.478 | 679.29 | 30.43 |
| multipath_carbon_persistence | — | 359.98 | 81.854 | 83.164 | 340.71 | 77.29 |
| service_first_gnn | 1 | 308.43 | 64.703 | 64.394 | 679.29 | 31.43 |
| service_first_gru | 1 | 308.43 | 64.696 | 64.381 | 679.29 | 31.71 |
| multipath_te_gnn | 1 | 401.98 | 84.716 | 86.281 | 246.43 | 99.57 |
| multipath_carbon_gnn | 1 | 359.91 | 81.659 | 82.939 | 345.00 | 75.71 |
| multipath_carbon_gru | 1 | 360.01 | 81.617 | 82.892 | 342.86 | 76.00 |
| perfect_service_first | — | 309.11 | 65.314 | 65.174 | 662.14 | 14.00 |
| perfect_multipath_carbon | — | 370.10 | 84.598 | 86.243 | 246.43 | 95.86 |
| perfect_multipath_te | — | 400.06 | 85.115 | 86.684 | 240.00 | 89.57 |

### ABILENE

Replay dates: 2004-06-01, 2004-06-02, 2004-06-03, 2004-06-04, 2004-06-05, 2004-06-06, 2004-06-07.

#### 10 Mbps / normal

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2168.43 | 77.763 | 83.529 | 62.14 | 0.00 |
| reactive_carbon | — | 1907.71 | 77.866 | 83.598 | 62.14 | 4.57 |
| equal_split | — | 2433.31 | 76.963 | 82.855 | 65.00 | 6.00 |
| service_first_persistence | — | 1893.72 | 77.851 | 83.567 | 62.14 | 5.43 |
| multipath_carbon_persistence | — | 1894.92 | 77.930 | 83.602 | 61.43 | 22.29 |
| service_first_gnn | 3 | 1893.72 | 77.850 | 83.567 | 62.14 | 5.52 |
| service_first_gru | 3 | 1893.70 | 77.847 | 83.565 | 62.14 | 5.71 |
| multipath_te_gnn | 1 | 2061.04 | 78.150 | 83.771 | 61.43 | 220.14 |
| multipath_carbon_gnn | 3 | 1894.91 | 77.929 | 83.602 | 61.43 | 21.95 |
| multipath_carbon_gru | 3 | 1894.80 | 77.921 | 83.599 | 61.43 | 22.00 |
| service_first_gnn_no_margin | 1 | 1894.75 | 77.849 | 83.566 | 62.14 | 6.57 |
| multipath_carbon_gnn_no_margin | 1 | 1894.95 | 77.931 | 83.602 | 61.43 | 22.29 |
| perfect_service_first | — | 1894.44 | 77.903 | 83.613 | 62.14 | 4.86 |
| perfect_multipath_carbon | — | 1895.45 | 77.998 | 83.645 | 61.43 | 25.00 |
| perfect_multipath_te | — | 2083.04 | 78.190 | 83.787 | 61.43 | 209.00 |

#### 10 Mbps / congested

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2150.70 | 76.046 | 82.248 | 75.00 | 0.00 |
| reactive_carbon | — | 1901.67 | 76.190 | 82.373 | 67.86 | 9.29 |
| equal_split | — | 2426.04 | 73.862 | 78.332 | 330.71 | 6.00 |
| service_first_persistence | — | 1885.91 | 76.155 | 82.329 | 71.43 | 10.29 |
| multipath_carbon_persistence | — | 1889.39 | 76.191 | 82.379 | 69.29 | 172.86 |
| service_first_gnn | 3 | 1885.89 | 76.153 | 82.319 | 73.57 | 10.10 |
| service_first_gru | 3 | 1885.66 | 76.150 | 82.307 | 76.43 | 8.57 |
| multipath_te_gnn | 1 | 2054.81 | 76.449 | 82.553 | 67.14 | 219.86 |
| multipath_carbon_gnn | 3 | 1888.94 | 76.189 | 82.376 | 69.29 | 166.19 |
| multipath_carbon_gru | 3 | 1888.57 | 76.187 | 82.373 | 69.29 | 157.14 |
| service_first_gnn_no_margin | 1 | 1886.51 | 76.142 | 82.299 | 77.86 | 10.29 |
| multipath_carbon_gnn_no_margin | 1 | 1888.29 | 76.180 | 82.370 | 70.00 | 125.86 |
| perfect_service_first | — | 1886.65 | 76.204 | 82.375 | 70.00 | 7.14 |
| perfect_multipath_carbon | — | 1889.57 | 76.216 | 82.404 | 67.86 | 132.71 |
| perfect_multipath_te | — | 2070.69 | 76.461 | 82.568 | 67.14 | 209.57 |

#### 10 Mbps / bursty

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2153.42 | 77.959 | 83.460 | 87.14 | 0.00 |
| reactive_carbon | — | 1927.39 | 78.042 | 83.666 | 88.57 | 35.00 |
| equal_split | — | 2425.31 | 75.838 | 80.334 | 195.71 | 6.00 |
| service_first_persistence | — | 1895.32 | 78.009 | 83.557 | 94.29 | 23.71 |
| multipath_carbon_persistence | — | 1892.36 | 78.029 | 83.580 | 87.14 | 149.57 |
| service_first_gnn | 3 | 1893.63 | 77.993 | 83.515 | 98.10 | 19.52 |
| service_first_gru | 3 | 1892.57 | 77.972 | 83.461 | 103.57 | 16.76 |
| multipath_te_gnn | 1 | 2044.09 | 78.405 | 84.019 | 70.00 | 341.14 |
| multipath_carbon_gnn | 3 | 1891.17 | 78.032 | 83.590 | 86.90 | 140.29 |
| multipath_carbon_gru | 3 | 1889.93 | 78.024 | 83.587 | 87.62 | 129.71 |
| service_first_gnn_no_margin | 1 | 1894.42 | 78.002 | 83.541 | 97.14 | 19.14 |
| multipath_carbon_gnn_no_margin | 1 | 1890.91 | 78.022 | 83.561 | 87.86 | 123.71 |
| perfect_service_first | — | 1901.91 | 78.186 | 83.824 | 76.43 | 18.00 |
| perfect_multipath_carbon | — | 1898.33 | 78.165 | 83.831 | 71.43 | 178.00 |
| perfect_multipath_te | — | 2056.75 | 78.458 | 84.072 | 69.29 | 303.57 |

#### 20 Mbps / normal

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2200.20 | 81.840 | 86.552 | 53.57 | 0.00 |
| reactive_carbon | — | 1926.67 | 81.905 | 86.612 | 53.57 | 5.43 |
| equal_split | — | 2444.01 | 81.115 | 85.939 | 55.00 | 6.00 |
| service_first_persistence | — | 1908.90 | 81.886 | 86.580 | 53.57 | 6.00 |
| multipath_carbon_persistence | — | 1909.95 | 81.955 | 86.629 | 52.86 | 22.71 |
| service_first_gnn | 1 | 1908.90 | 81.886 | 86.580 | 53.57 | 6.00 |
| service_first_gru | 1 | 1908.85 | 81.876 | 86.574 | 53.57 | 6.29 |
| multipath_te_gnn | 1 | 2083.57 | 82.135 | 86.770 | 52.86 | 220.57 |
| multipath_carbon_gnn | 1 | 1909.97 | 81.957 | 86.631 | 52.86 | 22.43 |
| multipath_carbon_gru | 1 | 1909.61 | 81.938 | 86.619 | 52.86 | 21.57 |
| perfect_service_first | — | 1909.75 | 81.935 | 86.629 | 53.57 | 4.57 |
| perfect_multipath_carbon | — | 1910.82 | 81.997 | 86.681 | 52.86 | 23.14 |
| perfect_multipath_te | — | 2107.38 | 82.142 | 86.786 | 52.86 | 209.43 |

#### 20 Mbps / congested

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2177.77 | 78.830 | 84.306 | 60.00 | 0.00 |
| reactive_carbon | — | 1913.10 | 78.927 | 84.373 | 59.29 | 5.14 |
| equal_split | — | 2436.15 | 78.096 | 83.661 | 61.43 | 6.00 |
| service_first_persistence | — | 1898.16 | 78.904 | 84.338 | 59.29 | 6.00 |
| multipath_carbon_persistence | — | 1899.46 | 78.976 | 84.379 | 59.29 | 22.57 |
| service_first_gnn | 1 | 1898.16 | 78.904 | 84.338 | 59.29 | 6.00 |
| service_first_gru | 1 | 1898.14 | 78.901 | 84.336 | 59.29 | 6.29 |
| multipath_te_gnn | 1 | 2073.29 | 79.196 | 84.541 | 58.57 | 219.29 |
| multipath_carbon_gnn | 1 | 1899.48 | 78.977 | 84.380 | 59.29 | 22.57 |
| multipath_carbon_gru | 1 | 1899.21 | 78.949 | 84.369 | 59.29 | 22.00 |
| perfect_service_first | — | 1898.96 | 78.963 | 84.387 | 59.29 | 4.57 |
| perfect_multipath_carbon | — | 1900.32 | 79.050 | 84.425 | 57.86 | 24.57 |
| perfect_multipath_te | — | 2090.10 | 79.230 | 84.557 | 57.86 | 209.14 |

#### 20 Mbps / bursty

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2183.72 | 81.357 | 86.544 | 55.71 | 0.00 |
| reactive_carbon | — | 1922.42 | 81.377 | 86.557 | 56.43 | 6.86 |
| equal_split | — | 2434.00 | 80.569 | 85.897 | 57.14 | 6.00 |
| service_first_persistence | — | 1907.64 | 81.350 | 86.514 | 56.43 | 9.43 |
| multipath_carbon_persistence | — | 1900.04 | 81.365 | 86.524 | 55.71 | 25.71 |
| service_first_gnn | 1 | 1907.64 | 81.350 | 86.514 | 56.43 | 9.43 |
| service_first_gru | 1 | 1907.62 | 81.345 | 86.511 | 56.43 | 8.86 |
| multipath_te_gnn | 1 | 2061.01 | 81.642 | 86.762 | 55.00 | 342.29 |
| multipath_carbon_gnn | 1 | 1900.06 | 81.367 | 86.526 | 55.71 | 25.71 |
| multipath_carbon_gru | 1 | 1899.80 | 81.354 | 86.518 | 55.71 | 23.43 |
| perfect_service_first | — | 1917.42 | 81.453 | 86.613 | 55.71 | 8.00 |
| perfect_multipath_carbon | — | 1901.33 | 81.438 | 86.602 | 55.00 | 25.86 |
| perfect_multipath_te | — | 2074.24 | 81.648 | 86.775 | 55.00 | 304.43 |

#### 40 Mbps / normal

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2234.96 | 88.117 | 91.154 | 39.29 | 0.00 |
| reactive_carbon | — | 1947.11 | 88.150 | 91.185 | 37.86 | 4.86 |
| equal_split | — | 2455.87 | 87.581 | 90.737 | 40.00 | 6.00 |
| service_first_persistence | — | 1926.36 | 88.139 | 91.164 | 38.57 | 5.43 |
| multipath_carbon_persistence | — | 1926.94 | 88.207 | 91.210 | 37.86 | 18.71 |
| service_first_gnn | 1 | 1926.36 | 88.139 | 91.164 | 38.57 | 5.43 |
| service_first_gru | 1 | 1926.31 | 88.126 | 91.148 | 38.57 | 5.43 |
| multipath_te_gnn | 1 | 2107.61 | 88.336 | 91.305 | 37.86 | 222.14 |
| multipath_carbon_gnn | 1 | 1926.96 | 88.209 | 91.212 | 37.86 | 18.43 |
| multipath_carbon_gru | 1 | 1926.81 | 88.195 | 91.202 | 38.57 | 17.86 |
| perfect_service_first | — | 1927.48 | 88.181 | 91.203 | 37.86 | 5.14 |
| perfect_multipath_carbon | — | 1927.21 | 88.253 | 91.253 | 37.86 | 20.43 |
| perfect_multipath_te | — | 2132.71 | 88.341 | 91.317 | 37.86 | 210.29 |

#### 40 Mbps / congested

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2211.93 | 83.633 | 87.893 | 49.29 | 0.00 |
| reactive_carbon | — | 1933.22 | 83.680 | 87.937 | 49.29 | 5.43 |
| equal_split | — | 2448.07 | 82.963 | 87.359 | 51.43 | 6.00 |
| service_first_persistence | — | 1914.77 | 83.666 | 87.913 | 49.29 | 6.29 |
| multipath_carbon_persistence | — | 1915.50 | 83.736 | 87.959 | 48.57 | 21.29 |
| service_first_gnn | 1 | 1914.77 | 83.666 | 87.913 | 49.29 | 6.29 |
| service_first_gru | 1 | 1914.72 | 83.652 | 87.905 | 49.29 | 5.71 |
| multipath_te_gnn | 1 | 2097.61 | 83.906 | 88.082 | 48.57 | 220.43 |
| multipath_carbon_gnn | 1 | 1915.52 | 83.737 | 87.960 | 48.57 | 21.14 |
| multipath_carbon_gru | 1 | 1915.36 | 83.720 | 87.949 | 49.29 | 20.29 |
| perfect_service_first | — | 1915.69 | 83.718 | 87.957 | 49.29 | 4.86 |
| perfect_multipath_carbon | — | 1915.77 | 83.785 | 88.005 | 49.29 | 22.14 |
| perfect_multipath_te | — | 2115.87 | 83.911 | 88.094 | 48.57 | 209.86 |

#### 40 Mbps / bursty

| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | — | 2217.53 | 86.617 | 90.480 | 44.29 | 0.00 |
| reactive_carbon | — | 1945.00 | 86.633 | 90.486 | 44.29 | 5.71 |
| equal_split | — | 2445.70 | 85.993 | 90.004 | 45.71 | 6.00 |
| service_first_persistence | — | 1926.66 | 86.606 | 90.443 | 44.29 | 8.00 |
| multipath_carbon_persistence | — | 1917.02 | 86.647 | 90.471 | 43.57 | 20.29 |
| service_first_gnn | 1 | 1926.66 | 86.606 | 90.443 | 44.29 | 8.00 |
| service_first_gru | 1 | 1925.78 | 86.602 | 90.433 | 44.29 | 7.43 |
| multipath_te_gnn | 1 | 2080.36 | 86.851 | 90.647 | 43.57 | 346.57 |
| multipath_carbon_gnn | 1 | 1917.05 | 86.649 | 90.472 | 43.57 | 20.29 |
| multipath_carbon_gru | 1 | 1916.86 | 86.629 | 90.460 | 44.29 | 19.29 |
| perfect_service_first | — | 1940.79 | 86.696 | 90.529 | 44.29 | 7.43 |
| perfect_multipath_carbon | — | 1917.58 | 86.725 | 90.544 | 43.57 | 22.00 |
| perfect_multipath_te | — | 2095.06 | 86.855 | 90.657 | 43.57 | 306.29 |

## Check 3: isolated perfect-demand comparison at reference capacity

Both columns use zero margin, the same planner and 10 Mbps capacity. Positive or negative differences are retained; perfect demand is not guaranteed to optimize these realized metrics.

| Network / workload / planner | Causal → perfect score | Causal → perfect pooled service % | Causal → perfect overload min/day |
| --- | ---: | ---: | ---: |
| geant / normal / service_first | 424.02 → 424.68 | 33.521 → 33.720 | 938.57 → 915.00 |
| geant / normal / multipath_carbon | 466.74 → 467.97 | 37.682 → 38.357 | 921.43 → 895.71 |
| geant / congested / service_first | 479.85 → 485.02 | 26.328 → 26.513 | 1058.57 → 975.00 |
| geant / congested / multipath_carbon | 523.66 → 527.76 | 25.217 → 25.453 | 1017.86 → 953.57 |
| geant / bursty / service_first | 454.85 → 459.59 | 28.440 → 28.730 | 1035.00 → 972.86 |
| geant / bursty / multipath_carbon | 491.68 → 496.39 | 30.036 → 30.673 | 1009.29 → 932.14 |
| abilene / normal / service_first | 1894.75 → 1894.44 | 77.849 → 77.903 | 62.14 → 62.14 |
| abilene / normal / multipath_carbon | 1894.95 → 1895.45 | 77.931 → 77.998 | 61.43 → 61.43 |
| abilene / congested / service_first | 1886.51 → 1886.65 | 76.142 → 76.204 | 77.86 → 70.00 |
| abilene / congested / multipath_carbon | 1888.29 → 1889.57 | 76.180 → 76.216 | 70.00 → 67.86 |
| abilene / bursty / service_first | 1894.42 → 1901.91 | 78.002 → 78.186 | 97.14 → 76.43 |
| abilene / bursty / multipath_carbon | 1890.91 → 1898.33 | 78.022 → 78.165 | 87.86 → 71.43 |

## Interpretation limits

Three seeds test initialization sensitivity, not universal GNN performance. Capacity sensitivity is conditional on declared scaled traffic and selected paths. Perfect-demand comparisons diagnose the existing objective and information pipeline; they do not prove an achievable improvement or a theoretical upper bound. Bootstrap day clusters average seeds within day; seven adjacent days remain seven clusters. The carbon score can change with the served traffic mix and is not a measured energy or emissions quantity. Retain these outcomes when writing or revising the paper.
