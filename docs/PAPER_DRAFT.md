# Graph Neural Network Driven Predictive Carbon Aware Routing with Congestion Safeguards in Software Defined Networks

**Working manuscript, 18 October 2026.** Ashutosh Gupta, Tanay Mohta, Avaneesh Chavan. This draft reports the current one-seed, five-day trace-driven evaluation. It is suitable for faculty discussion and needs broader validation, a verified bibliography and venue formatting before submission.

## Abstract

Carbon-aware routing can move traffic away from paths assigned high electricity carbon intensity, but competing flows may then overload shared links. We implement a trace-driven centralized routing simulation on an eight-node GÉANT subgraph using historical 15-minute traffic matrices and later, country-matched daily electricity carbon data. A compact graph convolution plus gated recurrent unit (GCN–GRU) predicts three future origin–destination demand matrices. Its predictions enter a path planner that removes old reservations before testing replacements, adds a validation-calibrated underprediction margin, and applies route-change hysteresis. We compare shortest-path routing, reactive carbon routing, predictive traffic engineering, persistence forecasting, and component ablations on identical held-out workloads. In congested cases with a one-bin observation lag, the proposed policy reduces mean overload duration from 126 to 114 minutes per day relative to reactive carbon routing, but increases the carbon-weighted forwarding score from 323.83 to 333.18. The same overload duration is achieved using persistence forecasting with the safeguards. Across three horizons, the GCN–GRU's mean held-out demand error is 0.4893 Mbps, versus 0.4858 for persistence and 0.4834 for a matched GRU. These results support the capacity-margin trade-off but do not establish a unique advantage from graph prediction. Carbon values represent attribution under a constructed temporal pairing, not measured network energy or emissions.

**Keywords:** software-defined networking; carbon-aware routing; graph neural networks; demand forecasting; traffic engineering; trace-driven simulation.

## 1. Introduction

Shortest-path traffic engineering is usually assessed in terms of network capacity and delay. Environmental objectives introduce another cost: the electricity carbon intensity associated with forwarding at different sites. Selecting a low-intensity path can shift demand to shared links, increasing overload and reducing service. A controller that knows only past demand is vulnerable when loads change faster than observations arrive.

We ask whether short-horizon demand prediction, paired with a conservative error allowance and shared capacity reservations, can manage that trade-off. The project implements the complete decision loop in a native Windows simulation and exposes every route and link load in a replay viewer. We use an actual GÉANT topology/traffic source and a public country-level carbon series, while keeping their differing calendar years explicit. The planned novelty is the *tested combination* of multi-horizon OD prediction, a validation-calibrated reservation margin, and hysteresis in carbon path choice. The components individually have prior art; this work does not claim to invent predictive routing or predictive carbon routing.

Three questions guide the evaluation: (RQ1) Does prediction reduce overload against a guarded reactive carbon policy with the same observation lag? (RQ2) What service and forwarding-score cost accompanies a validation-derived safety margin? (RQ3) Does graph aggregation improve demand prediction and routing compared with a matched no-graph GRU and persistence?

## 2. Related work and positioning

SNDlib provides a GÉANT instance and dynamic traffic matrices for network-design studies [1]. ECON-PowerCI estimates country-level daily consumption-based electricity CO2 intensity [2,3]. CIRo considers predictive carbon-aware routing [4], while NeuRoute studies predictive routing in SDNs [5]. These works make a general “first predictive carbon-aware SDN routing” claim inappropriate. Our narrower experimental contribution is to quantify the interaction of traffic forecast errors, conservative shared reservations and carbon choices under matched conditions. Complete bibliography fields and the SNDlib catalog's requested dynamic-data citations must be checked before submission.

## 3. Data and scenario construction

We retain eight GÉANT nodes—France, Germany, Belgium, Netherlands, Switzerland, Italy, Austria, Luxembourg—and the eleven physical links among them. Each physical link becomes two directed arcs with a configured 10 Mbps capacity per direction. We use source coordinates to assign a one-way propagation parameter: great-circle distance × 1.3 / 200 km/ms + 0.15 ms per hop. Neither these capacities nor delays are current GÉANT measurements.

The downloaded native archive contains 11,460 15-minute dynamic matrices from May to August 2005. We use 3,972 observed matrices from its first 42 calendar days. Chronological train, validation and test row splits are 0–2,382, 2,383–3,176 and 3,177–3,971. History and labels remain inside a split and are rejected if timestamps are discontinuous. A deterministic rule using training mean demand and shortest-route overlap chooses six active directed OD pairs with at least two delay-feasible paths. All inactive demands are masked; findings therefore concern the chosen subgraph traffic scenario, not all GÉANT traffic. A single factor fitted to training shortest-path loads scales demand so training p95 of peak link load reaches 70% of configured capacity.

Carbon comes from the daily ECON-PowerCI `Value` field. We map each node to its own country (FRA, DEU, BEL, NLD, CHE, ITA, AUT, LUX) and keep quality flags. Missing country-days are excluded. Luxembourg lacks coverage before June 2021, so we use 2022, 2023 and 2024 pairings. For each year, the nearest same-weekday date within three weeks of the 2005 month/day is selected if every country has complete coverage over the test interval. Daily intensity remains constant over 96 traffic bins. The units kg CO2/MWh and g CO2/kWh are numerically equal. Pairing 2005 traffic with later carbon is a constructed counterfactual scenario; it is not simultaneous observation or a reconstruction of operational emissions.

## 4. Prediction and path selection

Each graph node carries eight outgoing-demand features per bin. We concatenate local features with normalized-adjacency neighbor features, apply a 32-unit learned transform, and pass the sequence through a shared GRU. A residual head produces nonnegative predictions for 15, 30 and 45 minutes ahead. The GCN–GRU has 7,672 trainable parameters. A matched GRU replaces graph adjacency with identity; persistence repeats the latest matrix. Models train on active-pair MAE, use validation checkpoint selection, and never fit normalization to held-out rows.

For horizon \(h\), the safety allowance \(m_h\) is the validation 90th percentile of positive underprediction \(\max(y_h-\hat y_h,0)\), pooled across active pairs. The planner checks \(\hat y_h+m_h\) on future reservations. This is an empirical allowance, not a probabilistic service-level guarantee under distribution shift.

The controller candidate set contains up to three loop-free paths per pair, subject to a 1.5× shortest configured propagation bound. Pairs are processed in descending conservative demand. Before assessing a replacement, the planner subtracts the pair's old reservation from projected link loads; once selected, the new reservation immediately affects later pairs. Candidates whose own links exceed 80% projected utilization are rejected. Carbon modes rank feasible paths by the sum of forwarding-node carbon intensity. The predictive traffic-engineering baseline instead minimizes projected maximum utilization. A path change ordinarily needs a 5% objective improvement and a two-bin hold time; forecast risk on the current path overrides those elective guards. If no candidate passes the utilization check, the planner logs infeasibility and chooses minimum projected peak utilization.

For the primary experiment, all planners decide on bin \(k\) with observations only through \(k-1\). The GCN–GRU predicts \(k\) through \(k+2\); reactive routing repeats the last observed demand. Only after committing the routes does the replay reveal actual \(k\) demand. An immediate-observation sensitivity allows every policy to see \(k\). The one-bin lag models a 15-minute information delay in the experimental scenario; it does not measure actual SDN controller installation time. No future carbon day is given to the planner.

## 5. Service, environmental attribution and experiment protocol

Offered link rate is the sum of actual routed OD demands. A deterministic equal-rate progressive-filling allocator computes served flow rates while respecting each directed link's capacity. It is a fluid service model, not a packet queue, TCP goodput, loss or RTT measurement. Primary network measures are overload minutes (at least one offered link above 100%), p95/max offered utilization, integrated excess Mbit, served fraction, route changes and decision time.

We attribute carbon to **served** decimal megabytes. A flow served at \(s\) Mbps during one 900-second bin carries \(s\times900/8\) MB. Its path cost is the sum of the current g CO2/kWh values at each forwarding sender. The reported forwarding score is the served-byte-weighted path cost over the run. It is a normalized hop intensity score under an equal energy-per-byte convention, not grams of physical CO2. Separate hypothetical all-on idle and traffic-dependent power cases illustrate sensitivity; no empirical J/MB coefficient is supplied for the primary outcome. Served fraction is displayed beside every environmental comparison so load shedding cannot masquerade as an efficiency gain.

We compare four principal policies: fixed shortest path, guarded reactive carbon, GCN–GRU predictive traffic engineering and the proposed GCN–GRU carbon policy with margin/hysteresis. Component cases use persistence with its own margin, remove the margin, or remove hysteresis. The paper batch pairs each policy on five complete held-out days, three carbon-year alignments and three workloads: normal, 1.6× congested, and seeded three-bin 2.5× bursts on normal traffic. The delayed cases have seven policies, and immediate-observation cases have the four main policies: 495 successful runs in total. We take paired differences from the same workload/day/carbon realization. Descriptive confidence intervals resample five whole day clusters, averaging their three carbon pairings inside the cluster, rather than treating 15-minute bins as independent. Five adjacent days remain a weak basis for broad statistical inference.

## 6. Results

Mean active-pair test MAE across 15/30/45-minute horizons is 0.4893 Mbps for GCN–GRU, 0.4834 for the matched GRU and 0.4858 for persistence. At 15/30/45 minutes, GCN–GRU MAE is 0.3580 / 0.5021 / 0.6079 Mbps. Graph aggregation does not improve average forecast MAE in this run.

The table shows arithmetic means over five test days and three carbon-year pairings for the **one-bin-lag congested** workload. The carbon score is lower-is-better; it must be read with service.

| Policy | Carbon forwarding score | Served demand | Overload min/day | Changes/day |
|---|---:|---:|---:|---:|
| Shortest path | 419.36 | 91.22% | 165 | 0.0 |
| Reactive carbon | 323.83 | 91.89% | 126 | 19.4 |
| Predictive traffic engineering | 342.40 | 92.18% | 108 | 8.8 |
| Proposed GCN–GRU carbon | 333.18 | 91.92% | 114 | 18.2 |
| Persistence with safeguards | 338.58 | 91.98% | 114 | 23.0 |
| GCN–GRU carbon without margin | 321.30 | 91.88% | 129 | 17.0 |
| GCN–GRU carbon without hysteresis | 332.23 | 91.92% | 114 | 18.6 |

Relative to reactive carbon, the proposed policy changes overload by −12 minutes/day (descriptive day-cluster bootstrap interval −21 to −3) and carbon score by +9.35 (interval +2.83 to +16.56). The margin ablation has 129 overload minutes/day and a lower score of 321.30, illustrating the intended safety-versus-carbon trade-off. Persistence with the same safeguards also achieves 114 minutes/day, so this experiment does not isolate a superior GNN effect. Predictive traffic engineering has the lowest congested overload (108 minutes/day) but a higher carbon score than the proposed policy.

In the normal delayed workload, proposed and reactive overload both average 72 minutes/day, while the proposed score is higher by 5.24. Under seeded bursts the proposed policy averages 129 versus reactive 135 overload minutes/day, with a paired difference of −6 minutes/day whose descriptive interval (−21 to +6) spans zero. Its score is again higher by 12.09. Immediate observation narrows or removes the overload advantage: in congested cases both proposed and reactive average 108 minutes/day. These outcomes limit RQ1 to a conditional finding about the modeled information lag. The GNN's weaker MAE and the persistence ablation leave RQ3 unsupported in this run.

See `results/paper/figures/forecast_errors.pdf`, `carbon_overload_tradeoff.pdf`, `utilization_and_changes.pdf` and `components.pdf`, and the corresponding CSV/JSON run logs. The online-format table above comes from `results/paper/summary.csv`; per-bin records, configuration/source/checkpoint hashes and exact date pairings are stored in the campaign manifest.

## 7. Limitations and next validation

The subgraph is small and demand selection removes many real OD pairs. Capacities and propagation are configured assumptions. Daily country intensity is coarse and comes from later years than traffic; it cannot demonstrate a contemporary router's carbon emissions. Packet delay, loss, controller overhead and rule updates were not emulated. The safeguards are greedy and can fall back to infeasible paths. Five adjacent days and a single neural training seed limit uncertainty estimates and generalization. Forecast error calibration from normal validation data may be poorly covered under scaled congestion and modified bursts. Improvement thresholds and model size were fixed without a full validation-only policy search.

Before making a broader paper claim, rerun on more disjoint held-out windows and independent training seeds, assess several documented capacity and observation-delay settings without choosing favorable test cases, and validate packet behavior in a separately verified Mininet/OpenFlow experiment if feasible. Follow the SNDlib citation request and confirm all bibliography metadata. The current result is a completed reproducible simulation and a preliminary analysis, not evidence of operational carbon savings.

## References to complete before submission

1. [SNDlib GÉANT instance and dynamic matrices](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action), Poznan University of Technology. Dynamic archive metadata attributes the demand trace to Steve Uhlig. Retrieve the two full references requested by the SNDlib catalog.
2. Shujie Zhang, [ECON-PowerCI_2015_2024](https://doi.org/10.5281/zenodo.15987717), Zenodo, version 2, 2025.
3. [ECON-PowerCI methodology](https://www.nature.com/articles/s41597-025-05978-7), *Scientific Data*, 2025. Confirm full author list and article metadata.
4. [CIRo: predictive carbon-aware routing](https://netsec.ethz.ch/publications/papers/green_routing2023.pdf). Confirm final venue and bibliographic details.
5. [NeuRoute: predictive SDN routing](https://arxiv.org/abs/1709.06002). Confirm authors, version and venue.
