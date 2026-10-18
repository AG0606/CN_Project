# Measured results and interpretation

Generated from 495 successful paired runs; 0 failures.

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
| bursty / 0 | GNN + safeguards | 334.22 | 94.41% | 105.0 | 27.4 |
| bursty / 0 | Predictive TE | 366.95 | 94.41% | 105.0 | 12.6 |
| bursty / 0 | Reactive carbon | 321.59 | 94.41% | 105.0 | 23.0 |
| bursty / 0 | Shortest path | 421.46 | 93.12% | 147.0 | 0.0 |
| bursty / 1 | GNN without hysteresis | 326.02 | 93.76% | 138.0 | 29.0 |
| bursty / 1 | GNN without margin | 314.72 | 93.77% | 135.0 | 21.0 |
| bursty / 1 | Persistence + safeguards | 331.65 | 93.90% | 126.0 | 32.2 |
| bursty / 1 | GNN + safeguards | 328.81 | 93.86% | 129.0 | 27.8 |
| bursty / 1 | Predictive TE | 362.34 | 94.37% | 105.0 | 10.8 |
| bursty / 1 | Reactive carbon | 316.72 | 93.77% | 135.0 | 23.0 |
| bursty / 1 | Shortest path | 421.46 | 93.12% | 147.0 | 0.0 |
| congested / 0 | GNN + safeguards | 337.25 | 92.30% | 108.0 | 19.0 |
| congested / 0 | Predictive TE | 342.59 | 92.30% | 108.0 | 8.4 |
| congested / 0 | Reactive carbon | 327.53 | 92.30% | 108.0 | 19.0 |
| congested / 0 | Shortest path | 419.36 | 91.22% | 165.0 | 0.0 |
| congested / 1 | GNN without hysteresis | 332.23 | 91.92% | 114.0 | 18.6 |
| congested / 1 | GNN without margin | 321.30 | 91.88% | 129.0 | 17.0 |
| congested / 1 | Persistence + safeguards | 338.58 | 91.98% | 114.0 | 23.0 |
| congested / 1 | GNN + safeguards | 333.18 | 91.92% | 114.0 | 18.2 |
| congested / 1 | Predictive TE | 342.40 | 92.18% | 108.0 | 8.8 |
| congested / 1 | Reactive carbon | 323.83 | 91.89% | 126.0 | 19.4 |
| congested / 1 | Shortest path | 419.36 | 91.22% | 165.0 | 0.0 |
| normal / 0 | GNN + safeguards | 309.70 | 95.12% | 57.0 | 14.2 |
| normal / 0 | Predictive TE | 341.47 | 95.12% | 57.0 | 8.4 |
| normal / 0 | Reactive carbon | 305.56 | 95.12% | 57.0 | 10.6 |
| normal / 0 | Shortest path | 420.21 | 94.69% | 60.0 | 0.0 |
| normal / 1 | GNN without hysteresis | 307.33 | 94.94% | 72.0 | 15.0 |
| normal / 1 | GNN without margin | 302.72 | 94.91% | 72.0 | 10.2 |
| normal / 1 | Persistence + safeguards | 311.25 | 94.94% | 72.0 | 16.2 |
| normal / 1 | GNN + safeguards | 308.18 | 94.94% | 72.0 | 14.2 |
| normal / 1 | Predictive TE | 341.57 | 95.10% | 57.0 | 7.2 |
| normal / 1 | Reactive carbon | 302.93 | 94.91% | 72.0 | 10.6 |
| normal / 1 | Shortest path | 420.21 | 94.69% | 60.0 | 0.0 |

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
