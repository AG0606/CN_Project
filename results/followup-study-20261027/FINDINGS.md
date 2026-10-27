# Later-period training and routing evaluation

This is the first outcome evaluation on these later source periods in the recorded project experiments. The protocol, scientific code, prepared inputs and model hashes were frozen locally before final outcome evaluation. It is not an external preregistration. Training/checkpoint selection used only the declared earlier training and validation splits.

All declared variants are reported. One seed and seven adjacent test days per network limit generalization. Carbon is a forwarding attribution proxy, not measured emissions. Capacities and scaled/bursty workloads are simulation assumptions. GÉANT traffic is paired with 2022 daily country carbon; Abilene uses fixed 2004 annual regional EPA rates.

Variants: reference = original checkpoint; longer = original training/validation, up to 100 epochs; expanded = additional real training history and a later validation period; link_loss = same expanded data plus a 0.25-weighted shortest-path link-load error term. That term is a routing proxy, not end-to-end optimization. The original training-only pair set, rate multiplier and normalizer are fixed for every method.

## Outcome and source-quality warning

Twelve new neural checkpoints were actually trained (GNN and GRU, three variants, two networks), followed by all 630 declared routing runs. Longer training, additional history and the link-load loss did not consistently improve final forecast MAE. Lower routing carbon scores cannot be attributed to a proven GNN advantage.

There are 135 zero-offered policy runs. Three GÉANT replay days (30 June, 1 July and 2 July 2005) have no listed demands in the native source sections; 3 July also has 43 empty fifteen-minute sections out of 96. The full forecast test split additionally includes the empty 29 June. This does not establish genuinely zero network traffic or explain the cause. The fixed parser treats unlisted demands as zero; no days were removed, filled or replaced after observing outcomes. Carbon score is undefined when no bytes are served, so it is never treated as zero or as a carbon saving.

GÉANT's populated later days also strongly saturate the unchanged assumed capacities. This limits this comparison to a source-quality-limited stress test, not a clean confirmation of practical savings. Abilene has seven nonempty replay days, but also shows capacity pressure and mixed service/overload tradeoffs.

Carbon columns below average defined daily scores only, with their counts shown. Service is pooled served MB / offered MB over all seven days, avoiding the misleading 100% service convention for empty days. Overload, p95 and changes remain arithmetic means over all seven daily runs. An average daily p95 is not the p95 of the pooled observations.

See source_availability.csv and data_quality_audit.json for the post-evaluation source audit. The original frozen day_cluster_intervals.csv retains undefined GÉANT carbon differences/intervals: empty-day NaNs propagated, and its seven-cluster count includes three empty days. No GÉANT carbon confidence interval is claimed from those rows.

## GEANT

Test days: 2005-06-30, 2005-07-01, 2005-07-02, 2005-07-03, 2005-07-04, 2005-07-05, 2005-07-06.

Declared chronological splits: {'train': ['2005-05-04T15:00', '2005-06-14T23:45'], 'validation': ['2005-06-15T00:00', '2005-06-28T23:45'], 'test': ['2005-06-29T00:00', '2005-07-12T23:45']}.

### Training and validation

| Model | Selected epoch | Validation OD MAE (Mbps) | Training seconds |
| --- | ---: | ---: | ---: |
| reference_gnn | 36 | 0.35566 | 15.4 |
| reference_gru | 36 | 0.35367 | 14.8 |
| longer_gnn | 36 | 0.35566 | 22.6 |
| longer_gru | 56 | 0.35283 | 26.6 |
| expanded_gnn | 57 | 2.17965 | 44.2 |
| expanded_gru | 40 | 2.17940 | 32.0 |
| link_loss_gnn | 80 | 2.17738 | 60.8 |
| link_loss_gru | 39 | 2.17962 | 48.2 |

Validation values across different periods are not directly comparable; final test inputs are shared.

### Final forecast error

Forecast metrics cover all contiguous windows in the full declared test split. Routing below uses the first seven complete test days.

| Model | Horizon 1 MAE | Horizon 2 MAE | Horizon 3 MAE |
| --- | ---: | ---: | ---: |
| reference_gnn | 0.90815 | 1.13570 | 1.33218 |
| reference_gru | 0.88747 | 1.10722 | 1.28215 |
| longer_gnn | 0.90815 | 1.13570 | 1.33218 |
| longer_gru | 0.88858 | 1.10733 | 1.28141 |
| expanded_gnn | 0.91371 | 1.20356 | 1.41712 |
| expanded_gru | 0.89351 | 1.13752 | 1.33855 |
| link_loss_gnn | 0.92576 | 1.23801 | 1.49569 |
| link_loss_gru | 0.89527 | 1.13938 | 1.33951 |
| reference_persistence | 0.88971 | 1.11522 | 1.29519 |
| updated_persistence | 0.88971 | 1.11522 | 1.29519 |

### Routing: normal

All seven declared days retained; carbon uses defined days and service pools bytes. Read score alongside service and overload.

| Method | Carbon score | Score days | Pooled served % | Overload min/day | Mean daily p95 % | Changes/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 504.530 | 4/7 | 22.1484 | 681.43 | 203.66 | 0.00 |
| reactive_carbon | 429.462 | 4/7 | 22.5494 | 679.29 | 203.07 | 7.43 |
| predictive_carbon | 374.806 | 4/7 | 22.5506 | 679.29 | 203.07 | 7.43 |
| tradeoff_reactive | 272.326 | 4/7 | 22.5501 | 679.29 | 203.07 | 5.57 |
| oracle_current_bin | 270.297 | 4/7 | 22.5576 | 679.29 | 203.15 | 6.86 |
| tradeoff_reference_gnn | 270.430 | 4/7 | 22.5506 | 679.29 | 203.15 | 7.43 |
| tradeoff_reference_gru | 270.427 | 4/7 | 22.5506 | 679.29 | 203.15 | 7.43 |
| tradeoff_longer_gnn | 270.430 | 4/7 | 22.5506 | 679.29 | 203.15 | 7.43 |
| tradeoff_longer_gru | 270.430 | 4/7 | 22.5506 | 679.29 | 203.15 | 7.43 |
| tradeoff_expanded_gnn | 270.349 | 4/7 | 22.5473 | 679.29 | 203.15 | 8.86 |
| tradeoff_expanded_gru | 270.353 | 4/7 | 22.5473 | 679.29 | 203.15 | 8.71 |
| tradeoff_link_loss_gnn | 270.358 | 4/7 | 22.5481 | 679.29 | 203.15 | 8.86 |
| tradeoff_link_loss_gru | 270.361 | 4/7 | 22.5480 | 679.29 | 203.15 | 8.43 |
| tradeoff_reference_persistence | 270.611 | 4/7 | 22.5506 | 679.29 | 203.15 | 7.43 |
| tradeoff_updated_persistence | 270.728 | 4/7 | 22.5506 | 679.29 | 203.15 | 7.43 |

### Routing: congested

All seven declared days retained; carbon uses defined days and service pools bytes. Read score alongside service and overload.

| Method | Carbon score | Score days | Pooled served % | Overload min/day | Mean daily p95 % | Changes/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 526.383 | 4/7 | 15.7431 | 696.43 | 325.86 | 0.00 |
| reactive_carbon | 454.079 | 4/7 | 16.1565 | 696.43 | 324.92 | 7.14 |
| predictive_carbon | 407.418 | 4/7 | 16.1572 | 696.43 | 324.92 | 8.00 |
| tradeoff_reactive | 317.069 | 4/7 | 16.1576 | 696.43 | 324.92 | 5.00 |
| oracle_current_bin | 314.858 | 4/7 | 16.1628 | 696.43 | 325.04 | 5.43 |
| tradeoff_reference_gnn | 315.378 | 4/7 | 16.1572 | 696.43 | 325.04 | 7.14 |
| tradeoff_reference_gru | 315.378 | 4/7 | 16.1572 | 696.43 | 325.04 | 7.14 |
| tradeoff_longer_gnn | 315.378 | 4/7 | 16.1572 | 696.43 | 325.04 | 7.14 |
| tradeoff_longer_gru | 315.378 | 4/7 | 16.1572 | 696.43 | 325.04 | 7.14 |
| tradeoff_expanded_gnn | 315.356 | 4/7 | 16.1561 | 696.43 | 325.04 | 7.43 |
| tradeoff_expanded_gru | 315.356 | 4/7 | 16.1561 | 696.43 | 325.04 | 7.43 |
| tradeoff_link_loss_gnn | 315.354 | 4/7 | 16.1564 | 696.43 | 325.04 | 7.14 |
| tradeoff_link_loss_gru | 315.356 | 4/7 | 16.1561 | 696.43 | 325.04 | 7.43 |
| tradeoff_reference_persistence | 315.378 | 4/7 | 16.1572 | 696.43 | 325.04 | 7.14 |
| tradeoff_updated_persistence | 315.378 | 4/7 | 16.1572 | 696.43 | 325.04 | 7.14 |

### Routing: bursty

All seven declared days retained; carbon uses defined days and service pools bytes. Read score alongside service and overload.

| Method | Carbon score | Score days | Pooled served % | Overload min/day | Mean daily p95 % | Changes/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 516.604 | 4/7 | 18.2200 | 687.86 | 235.50 | 0.00 |
| reactive_carbon | 439.581 | 4/7 | 18.5952 | 685.71 | 234.94 | 7.14 |
| predictive_carbon | 393.388 | 4/7 | 18.5952 | 685.71 | 234.94 | 7.43 |
| tradeoff_reactive | 296.827 | 4/7 | 18.5955 | 685.71 | 234.94 | 5.00 |
| oracle_current_bin | 294.814 | 4/7 | 18.6006 | 685.71 | 235.01 | 6.57 |
| tradeoff_reference_gnn | 295.125 | 4/7 | 18.5952 | 685.71 | 235.01 | 7.14 |
| tradeoff_reference_gru | 295.007 | 4/7 | 18.5952 | 685.71 | 235.01 | 7.14 |
| tradeoff_longer_gnn | 295.125 | 4/7 | 18.5952 | 685.71 | 235.01 | 7.14 |
| tradeoff_longer_gru | 295.106 | 4/7 | 18.5952 | 685.71 | 235.01 | 7.14 |
| tradeoff_expanded_gnn | 295.036 | 4/7 | 18.5927 | 685.71 | 235.01 | 8.29 |
| tradeoff_expanded_gru | 295.068 | 4/7 | 18.5927 | 685.71 | 235.01 | 8.00 |
| tradeoff_link_loss_gnn | 295.043 | 4/7 | 18.5933 | 685.71 | 235.01 | 8.29 |
| tradeoff_link_loss_gru | 295.077 | 4/7 | 18.5925 | 685.71 | 235.01 | 8.00 |
| tradeoff_reference_persistence | 295.125 | 4/7 | 18.5952 | 685.71 | 235.01 | 7.14 |
| tradeoff_updated_persistence | 295.151 | 4/7 | 18.5952 | 685.71 | 235.01 | 7.14 |
## ABILENE

Test days: 2004-05-02, 2004-05-03, 2004-05-04, 2004-05-05, 2004-05-06, 2004-05-07, 2004-05-08.

Declared chronological splits: {'train': ['2004-03-01T00:00', '2004-04-15T23:55'], 'validation': ['2004-04-22T00:00', '2004-04-28T23:55'], 'test': ['2004-05-01T00:00', '2004-05-14T23:55']}.

### Training and validation

| Model | Selected epoch | Validation OD MAE (Mbps) | Training seconds |
| --- | ---: | ---: | ---: |
| reference_gnn | 1 | 0.08777 | 6.6 |
| reference_gru | 12 | 0.08699 | 17.8 |
| longer_gnn | 25 | 0.08573 | 49.9 |
| longer_gru | 12 | 0.08699 | 25.6 |
| expanded_gnn | 22 | 0.15164 | 64.4 |
| expanded_gru | 52 | 0.14885 | 115.3 |
| link_loss_gnn | 28 | 0.15087 | 64.1 |
| link_loss_gru | 55 | 0.14879 | 102.2 |

Validation values across different periods are not directly comparable; final test inputs are shared.

### Final forecast error

Forecast metrics cover all contiguous windows in the full declared test split. Routing below uses the first seven complete test days.

| Model | Horizon 1 MAE | Horizon 2 MAE | Horizon 3 MAE |
| --- | ---: | ---: | ---: |
| reference_gnn | 0.26305 | 0.36679 | 0.41924 |
| reference_gru | 0.28676 | 0.40153 | 0.46217 |
| longer_gnn | 0.30178 | 0.42543 | 0.49064 |
| longer_gru | 0.28676 | 0.40153 | 0.46217 |
| expanded_gnn | 0.28313 | 0.41260 | 0.47263 |
| expanded_gru | 0.28068 | 0.43175 | 0.48577 |
| link_loss_gnn | 0.27807 | 0.40204 | 0.46377 |
| link_loss_gru | 0.27729 | 0.41601 | 0.48276 |
| reference_persistence | 0.26326 | 0.36706 | 0.41975 |
| updated_persistence | 0.26326 | 0.36706 | 0.41975 |

### Routing: normal

All seven declared days retained; carbon uses defined days and service pools bytes. Read score alongside service and overload.

| Method | Carbon score | Score days | Pooled served % | Overload min/day | Mean daily p95 % | Changes/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2133.750 | 7/7 | 74.8143 | 157.14 | 72.55 | 0.00 |
| reactive_carbon | 1905.068 | 7/7 | 74.8599 | 157.14 | 74.74 | 15.00 |
| predictive_carbon | 1899.509 | 7/7 | 74.8556 | 157.14 | 74.63 | 14.00 |
| tradeoff_reactive | 1898.797 | 7/7 | 74.8498 | 157.14 | 74.89 | 18.86 |
| oracle_current_bin | 1897.925 | 7/7 | 75.0065 | 156.43 | 76.16 | 18.86 |
| tradeoff_reference_gnn | 1891.977 | 7/7 | 74.8458 | 157.14 | 74.79 | 16.86 |
| tradeoff_reference_gru | 1890.601 | 7/7 | 74.8480 | 157.14 | 74.76 | 15.14 |
| tradeoff_longer_gnn | 1891.941 | 7/7 | 74.8506 | 157.14 | 74.79 | 15.71 |
| tradeoff_longer_gru | 1890.601 | 7/7 | 74.8480 | 157.14 | 74.76 | 15.14 |
| tradeoff_expanded_gnn | 1892.655 | 7/7 | 74.8503 | 157.14 | 74.67 | 15.57 |
| tradeoff_expanded_gru | 1888.907 | 7/7 | 74.8427 | 157.14 | 74.58 | 16.14 |
| tradeoff_link_loss_gnn | 1889.476 | 7/7 | 74.8429 | 157.14 | 74.58 | 17.00 |
| tradeoff_link_loss_gru | 1888.458 | 7/7 | 74.8389 | 157.14 | 74.53 | 17.00 |
| tradeoff_reference_persistence | 1891.689 | 7/7 | 74.8461 | 157.14 | 74.78 | 16.29 |
| tradeoff_updated_persistence | 1889.331 | 7/7 | 74.8405 | 157.14 | 74.70 | 16.86 |

### Routing: congested

All seven declared days retained; carbon uses defined days and service pools bytes. Read score alongside service and overload.

| Method | Carbon score | Score days | Pooled served % | Overload min/day | Mean daily p95 % | Changes/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2095.460 | 7/7 | 71.7882 | 169.29 | 116.07 | 0.00 |
| reactive_carbon | 1956.836 | 7/7 | 71.8851 | 177.14 | 114.77 | 41.57 |
| predictive_carbon | 1958.371 | 7/7 | 71.8964 | 173.57 | 114.40 | 39.43 |
| tradeoff_reactive | 1930.396 | 7/7 | 71.8880 | 173.57 | 116.06 | 71.86 |
| oracle_current_bin | 1870.403 | 7/7 | 71.9783 | 166.43 | 121.09 | 50.57 |
| tradeoff_reference_gnn | 1921.791 | 7/7 | 71.8901 | 173.57 | 116.10 | 65.29 |
| tradeoff_reference_gru | 1919.459 | 7/7 | 71.8880 | 173.57 | 116.08 | 54.71 |
| tradeoff_longer_gnn | 1921.972 | 7/7 | 71.8882 | 172.86 | 115.98 | 57.00 |
| tradeoff_longer_gru | 1919.459 | 7/7 | 71.8880 | 173.57 | 116.08 | 54.71 |
| tradeoff_expanded_gnn | 1921.217 | 7/7 | 71.8920 | 173.57 | 116.07 | 54.71 |
| tradeoff_expanded_gru | 1916.584 | 7/7 | 71.8901 | 174.29 | 116.08 | 51.00 |
| tradeoff_link_loss_gnn | 1915.610 | 7/7 | 71.8885 | 175.00 | 116.06 | 52.14 |
| tradeoff_link_loss_gru | 1916.132 | 7/7 | 71.8886 | 174.29 | 116.05 | 52.43 |
| tradeoff_reference_persistence | 1921.326 | 7/7 | 71.8902 | 174.29 | 116.10 | 65.29 |
| tradeoff_updated_persistence | 1917.546 | 7/7 | 71.8871 | 174.29 | 116.09 | 64.14 |

### Routing: bursty

All seven declared days retained; carbon uses defined days and service pools bytes. Read score alongside service and overload.

| Method | Carbon score | Score days | Pooled served % | Overload min/day | Mean daily p95 % | Changes/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_path | 2109.223 | 7/7 | 71.0554 | 307.86 | 94.59 | 0.00 |
| reactive_carbon | 1963.753 | 7/7 | 71.1268 | 309.29 | 94.41 | 93.29 |
| predictive_carbon | 1962.633 | 7/7 | 71.1270 | 307.86 | 93.95 | 99.43 |
| tradeoff_reactive | 1936.222 | 7/7 | 71.1715 | 306.43 | 94.87 | 112.57 |
| oracle_current_bin | 1912.097 | 7/7 | 71.7540 | 247.86 | 96.99 | 78.86 |
| tradeoff_reference_gnn | 1927.791 | 7/7 | 71.1637 | 305.00 | 94.61 | 108.86 |
| tradeoff_reference_gru | 1912.594 | 7/7 | 71.1479 | 315.71 | 95.02 | 94.86 |
| tradeoff_longer_gnn | 1906.495 | 7/7 | 71.1435 | 319.29 | 95.26 | 88.29 |
| tradeoff_longer_gru | 1912.594 | 7/7 | 71.1479 | 315.71 | 95.02 | 94.86 |
| tradeoff_expanded_gnn | 1910.748 | 7/7 | 71.1489 | 314.29 | 95.09 | 95.00 |
| tradeoff_expanded_gru | 1907.299 | 7/7 | 71.1708 | 311.43 | 95.13 | 91.00 |
| tradeoff_link_loss_gnn | 1908.980 | 7/7 | 71.1639 | 312.86 | 94.99 | 95.14 |
| tradeoff_link_loss_gru | 1908.592 | 7/7 | 71.1793 | 310.00 | 95.15 | 91.29 |
| tradeoff_reference_persistence | 1927.845 | 7/7 | 71.1637 | 305.00 | 94.61 | 108.86 |
| tradeoff_updated_persistence | 1924.915 | 7/7 | 71.1700 | 304.29 | 94.54 | 108.57 |

## Interpretation rules

The oracle sees actual current demand and has no switching penalty. It is a diagnostic and is not deployable. Its offered-demand objective is not a guaranteed lower bound on the reported served-byte daily score.

The planner's carbon and peak guards use forecasts. Zero predicted guard violations do not guarantee actual service, overload or carbon performance. Day-cluster bootstrap intervals in day_cluster_intervals.csv are descriptive with only seven adjacent day clusters. Do not tune a method against these final outcomes and call a rerun an independent test.
