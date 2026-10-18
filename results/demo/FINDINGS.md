# Measured results and interpretation

Generated from 14 successful paired runs; 0 failures.

## Forecast accuracy

Mean MAE over the three horizons, active pairs only:

- gnn: 0.4893 Mbps.
- gru: 0.4834 Mbps.
- persistence: 0.4858 Mbps.

The GNN does **not** beat persistence on mean held-out MAE in this run. Do not claim otherwise.

The no-graph GRU has lower mean held-out MAE; this run does not establish a benefit from graph aggregation.

## Routing (arithmetic mean across paired day/carbon realizations)

| Scenario / lag | Policy | Forwarding score | Served | Overload min/day | Changes/day |
|---|---|---:|---:|---:|---:|
| congested / 1 | GNN without hysteresis | 520.77 | 99.44% | 60.0 | 22.0 |
| congested / 1 | GNN without margin | 509.67 | 99.35% | 90.0 | 20.0 |
| congested / 1 | Persistence + safeguards | 520.68 | 99.44% | 60.0 | 22.0 |
| congested / 1 | GNN + safeguards | 520.64 | 99.44% | 60.0 | 22.0 |
| congested / 1 | Predictive TE | 548.93 | 99.44% | 60.0 | 6.0 |
| congested / 1 | Reactive carbon | 511.57 | 99.36% | 75.0 | 24.0 |
| congested / 1 | Shortest path | 613.67 | 98.55% | 165.0 | 0.0 |
| normal / 1 | GNN without hysteresis | 453.92 | 99.92% | 15.0 | 26.0 |
| normal / 1 | GNN without margin | 446.70 | 99.92% | 15.0 | 14.0 |
| normal / 1 | Persistence + safeguards | 461.21 | 99.92% | 15.0 | 28.0 |
| normal / 1 | GNN + safeguards | 455.58 | 99.92% | 15.0 | 24.0 |
| normal / 1 | Predictive TE | 553.32 | 100.00% | 0.0 | 6.0 |
| normal / 1 | Reactive carbon | 447.55 | 99.92% | 15.0 | 16.0 |
| normal / 1 | Shortest path | 611.22 | 100.00% | 0.0 | 0.0 |

## What these results establish

The implementation runs an actual GCN–GRU and compares causal routing policies on identical trace-derived workloads. The marginal value of the model and each safeguard must be judged from paired_differences.csv and the component rows. A lower forwarding score alone is not evidence of reduced physical network electricity use.

## Evidence limits

- Traffic is from 2005, paired by weekday and season with 2022–2024 carbon. These are constructed scenarios, not simultaneous observations.
- Daily carbon is held constant over each day and the planning horizon. No carbon forecasting or subhourly grid observations.
- Eight nodes and six training-selected directed OD pairs; configured capacities/delays, one model seed.
- Aggregate max-min service, not TCP goodput, packet loss or RTT. One-bin lag means 15 scenario minutes.
- Forwarding score sums sender CI over hops, weighted by served bytes. Hypothetical idle/beta models are sensitivity examples only.
- The paper campaign uses five adjacent held-out days. Window-clustered bootstrap intervals are descriptive and adjacent days may still correlate.
- No Mininet/OpenFlow actuation was run. Publication novelty and generalization are not established by this implementation.

## Reproduction

See manifest.json, alignment_*.json, runs/*.json, summary.csv and figures/. The manifest records input/model/config/source hashes. Repeated deterministic runs do not create additional independent evidence.
