# Implemented methodology

## Scope and research question

Can demand forecasting with an empirical underprediction margin reduce overload while preserving a lower forwarding carbon score? The implementation evaluates a combination of established techniques. It does not claim a verified first-ever method, a guarantee of latency compliance, or publication readiness.

## Data and splits

The full native GÉANT archive is read sequentially without extracting members to disk. Each source matrix must declare `15min` and `MBITPERSEC`. Duplicate timestamps, duplicate retained demands, nonfinite/negative rates and non-unit routing units fail. Absent OD entries are zero according to the scenario interpretation of an unlisted SNDlib demand; the omission count is recorded. Missing timestamps are not interpolated.

Use the first 42 calendar days of available traffic (3,972 observed bins in the verified download). Chronological row boundaries are 0, 2,383, 3,177, 3,972. Every training, validation and forecast-test window keeps its 12 history bins and 3 targets within its own split and a contiguous 15-minute sequence. This yields 2,369 / 780 / 781 windows.

Among OD pairs with at least two candidates within the delay bound, select six greedily by training mean demand multiplied by `1 + .25 * shared_shortest_route_links`. This favors nontrivial competing routes without looking at carbon or held-out demand. The selected pairs are IT→NL, IT→FR, DE→BE, NL→FR, NL→IT, CH→DE. Mask all other flows in training and replay while preserving full extracted matrices separately.

Scale all traffic by one common factor, chosen so training p95 of the maximum shortest-path link load is 70% of 10 Mbps. The first verified factor is approximately 0.01554737. Per-OD normalization is its training 95th percentile, floored at 0.01 Mbps. No test statistic affects scaling or pair selection.

Normal load uses factor 1; congested uses 1.6. Bursty uses normal load plus seeded per-pair arrivals with probability .08 per bin, multiplying three bins by 2.5 (overlaps do not compound). These modified traces are labelled. Their observed past is visible to every policy; future bursts are not announced. Configured routing/load settings were fixed before examining test routing outcomes; they were not optimized for a favorable test result.

## Country carbon and temporal mismatch

ECON-PowerCI is daily consumption-based country carbon intensity, in kg CO2/MWh, numerically equal to g CO2/kWh. The field is `Value`; quality `FLAG` values N/F are retained. Use FRA, DEU, BEL, NLD, CHE, ITA, AUT, LUX in fixed node order. Missing country-days exclude a carbon period; no neighboring-country substitution or interpolation.

Luxembourg is missing before June 2021, so the implemented three pairings use **2022, 2023, 2024**. For each year choose the nearest date within ±21 days of the same month/day that has the same weekday and complete eight-country coverage over the full test interval. Selection uses calendar and availability, not carbon contrast. Every country uses the same paired date. The alignment JSON records both original calendars, values and flags.

These are constructed scenarios: 2005 traffic and later carbon are not simultaneous measurements. Source traffic timezone is unspecified; naive source dates are preserved without claiming UTC alignment. Daily carbon remains constant across 96 traffic bins. The planner holds current carbon over its entire horizon, including across midnight; future carbon is never supplied. Daily averages are retrospective scenario inputs, not real-time forecasts.

## Graph, model and uncertainty margin

Eleven retained physical links become 22 directed arcs, each 10 Mbps. A link's assumed one-way propagation is `haversine_km * 1.3 / 200 + .15` milliseconds: a 200 km/ms fiber speed, route-length stretch and per-hop processing allowance. These are experimental assumptions, not source-measured GÉANT capacities or delays.

For each bin, node `i` has eight outgoing-demand features. Concatenate its local vector with `A_norm X`, where `A_norm = D^-1/2 (A+I) D^-1/2`. A learned linear layer and ReLU produce 32 features, followed by a shared node-wise GRU over 12 bins. A linear head predicts corrections to the latest observed OD vector for three horizons; clamp nonnegative and apply the active mask. The model has 7,672 trainable parameters.

The matched GRU substitutes identity adjacency and otherwise retains identical architecture/parameter count. Persistence repeats the last observation. Both neural models use Adam (0.001), batch size 128, at most 40 epochs, patience 8, fixed seed 42 and CPU execution. Optimize active-pair MAE in Mbps. Select checkpoints by validation MAE, never test score.

For each horizon, pool `max(actual - predicted, 0)` across validation windows and active pairs. The 90th percentile is added to each active forecast for conservative capacity checks. Persistence receives its own separately calibrated margin in its component comparison. Do not interpret empirical coverage as a formal guarantee, especially under scaled/bursty test conditions. High-load forecasting error uses the training target 90th percentile threshold.

## Routing and causal timing

Precompute up to three shortest simple paths by assumed propagation, retaining those within 1.5 times the shortest path delay. Start every run on shortest paths. Process active OD pairs in descending maximum conservative forecast demand, with stable pair-index ties.

For each pair, remove its existing future reservation, test each candidate, then immediately add the selected reservation back. A candidate is capacity-feasible when its own links are at most 80% utilized across the three horizons. An unrelated overloaded link does not automatically disqualify a candidate. Among feasible paths, carbon policies minimize the sum of forwarding-sender CI, with deterministic ties. Predictive TE minimizes global projected peak utilization without carbon. If none is feasible, choose the minimum global peak (then candidate peak) and log infeasibility. The delay bound remains enforced because all candidates already satisfy it.

Elective rerouting requires 5% objective improvement and a two-bin hold time. Current-path forecast capacity risk overrides those elective guards. The no-hysteresis component removes both the hold time and improvement threshold. All policies share candidate paths, rates, capacities, timing and allocator.

At target bin k with one-bin lag, the latest observation is k−1. The model predicts k through k+2; reactive routing repeats k−1. Routes are committed before actual k is revealed to the service engine. The `predict`/`decide` interfaces receive no future rows. With immediate observations, every policy sees k; the proposed policy combines known k with predictions of k+1 and k+2. This lag abstraction must not be presented as measured SDN controller delay.

## Service and accounting

For each directed link, offered rate is the sum of routed flow demands. Equal-rate progressive filling allocates each flow until it reaches its demand or a link saturates; remaining flows continue until frozen. This is a deterministic fluid max-min approximation, not TCP or a packet queue. Unserved demand is service deficit, not measured packet loss.

For served flow rate `s` Mbps over a 900-second bin, decimal MB = `s*900/8`. Path carbon cost is the sum of current CI at each forwarding sender; the final destination is not charged an additional forwarding hop. The headline score is `sum(served_MB * path_cost) / sum(served_MB)` over the complete run, not a mean of per-bin ratios. Its unit is a sum of g CO2/kWh over forwarding hops. It implies equal hop-energy attribution and is not grams emitted.

Optional explicitly assumed `epsilon` J/MB converts to modeled grams using `sum(served_MB * path_cost)*epsilon/3,600,000`. No empirical epsilon is supplied in the headline experiments. For sensitivity only, all routers stay on with `P_i = idle_W + beta_W_per_Mbps * served_outgoing_Mbps`. Cases `(50,0)`, `(50,.1)`, `(5,1)` are hypothetical. Beta=0 must be route-invariant for matched inputs. Service fraction must accompany any environmental comparison.

## Experiment design and inference limits

Seven delayed policies: shortest path, reactive carbon, predictive TE, GNN with margin/hysteresis, persistence with its margin/hysteresis, GNN without margin, GNN without hysteresis. Four main policies also run with immediate observations. The paper batch uses the first five complete held-out calendar days, three calendar-selected carbon pairings and three workloads, totalling 495 runs. Neural forecast test metrics additionally cover all 781 valid test windows.

Report max/p95 offered link utilization (p95 over every link-bin cell, including idle links), network-overload minutes (any link >100%), sum of excess Mbit over link-bins, service fraction, byte-weighted carbon score, infeasible pair-bin count, route changes and timed prediction-plus-planning milliseconds. No packet latency quantile is computed.

For each workload/lag, pair each policy against reactive routing by day and carbon year. Average differences over carbon pairings inside a day, then resample whole day clusters 2,000 times for descriptive 95% percentile intervals. The pilot has only one day and no interval. Five adjacent days are few and potentially autocorrelated; intervals are not proof of broad significance. Re-running identical inputs with another label is not another independent sample.

Current evidence does not show GNN superiority over persistence or the matched GRU. A defensible paper can report the congestion/carbon trade-off and limits of adding prediction, but stronger novelty claims need additional held-out periods, training seeds and related-work review. Extend the same approach without selecting tests to manufacture gains.
