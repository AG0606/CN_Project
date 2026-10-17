# Implementation plan for GÉANT predictive carbon aware routing

Planning baseline: 8 October 2026. Implementation status updated 17 October 2026: the agreed native Windows simulation is built, real inputs are cached, the GNN and GRU are trained, and a 495-run comparison has been executed. Start with [README.md](README.md) and [DEMO.html](DEMO.html). The dates below record the original schedule; October 14 is now past. Optional Mininet remains unimplemented.

## Agreed direction and deadlines

Build a native Windows Python simulation of predictive carbon-aware routing on an eight-node GÉANT subgraph. Use historical GÉANT traffic matrices and geographically matched European country carbon data. The demonstration is due Wednesday 14 October 2026. Use the additional two weeks, approximately 15–28 October, for repeated experiments, stronger validation, and a research-paper draft.

This is the sole implementation approach in this document. No alternative implementation path or separate backup plan is maintained.

Mininet is an optional extension of this same system during the paper phase, rather than a prerequisite for the October 14 demo. The simulation represents a centralized SDN routing decision loop; actual OpenFlow actuation must only be claimed if the Mininet extension is implemented and verified.

All project tools and data access must be free. Use downloadable files and local computation. Do not depend on paid APIs, subscriptions, expiring commercial trials, or paid cloud infrastructure. The demo must work without internet after input preparation.

The strongest laptop reportedly has about 24 GB RAM and runs Windows. The user's laptop has 8 GB RAM. CPU details and available daily hours are not confirmed. Keep the model small, automate execution, and minimize hands-on work without dropping the GNN or the contribution experiment.

Suggested title: Graph Neural Network Driven Predictive Carbon Aware Routing with Congestion Safeguards in Software Defined Networks. Revise the abstract to describe trace-driven simulation as the completed evaluation; add Mininet only when it is actually completed.

## Research question and contribution

Research question: when cleaner routes share constrained links, can short-horizon GNN traffic prediction and a validation-calibrated error margin reduce overload while retaining lower modeled forwarding carbon intensity?

The proposed modification combines multi-step GNN demand prediction, conservative capacity reservation, carbon-aware candidate-path selection, and route-change hysteresis. Its contribution is a reproducible experimental evaluation of this combination, particularly the effect of the error margin. These ingredients are established individually; do not claim a verified first-ever algorithm or an empty literature quadrant.

CIRo already forecasts path carbon intensity, and NeuRoute establishes predictive SDN routing as prior work. Distinguish this project's traffic forecasting and congestion safeguards from those earlier contributions.

Test the following hypotheses rather than assume favorable outcomes:

- Prediction may reduce overload when demand growth is predictable and decisions use delayed observations.
- An empirical error margin may make routing more robust to underprediction, with a cost in carbon opportunities or path length.
- Under unexpected bursts or immediate observation, prediction may offer little improvement or perform worse.

Use a reasonably guarded reactive carbon comparator. Forecasting must not receive credit for safeguards that the baseline lacks. Separate the effect of the GNN, error margin, and hysteresis through component-removal experiments.

## Dataset and topology

### Eight-node GÉANT subgraph

Use these original SNDlib node IDs, with the following fixed order:

| Index | Node ID | Country | Carbon code |
|---|---|---|---|
| 0 | fr1.fr | France | FR |
| 1 | de1.de | Germany | DE |
| 2 | be1.be | Belgium | BE |
| 3 | nl1.nl | Netherlands | NL |
| 4 | ch1.ch | Switzerland | CH |
| 5 | it1.it | Italy | IT |
| 6 | at1.at | Austria | AT |
| 7 | lu1.lu | Luxembourg | LU |

Keep all eleven original links between retained nodes:

- France–Germany, France–Belgium, France–Switzerland, France–Luxembourg.
- Belgium–Netherlands, Belgium–Luxembourg, Germany–Netherlands.
- Switzerland–Italy, Germany–Italy, Switzerland–Austria, Germany–Austria.

Model each physical link as two directed edges with explicitly configured capacity per direction. Preserve the source IDs and graph hash in every artifact. Do not confuse demands with links: an 8-by-8 OD matrix has 56 off-diagonal entries; the graph has eleven physical links.

The full SNDlib instance has 22 nodes and 36 links. We are evaluating a selected GÉANT subgraph, not reproducing the whole backbone. Retained demand pairs can have fewer available routes after extraction. Capacities and delays will be experimental parameters, not assumed measurements of today's GÉANT network.

### Historical traffic

Download the free SNDlib dynamic GÉANT archive from the PUT mirror. The catalog lists fifteen-minute matrices across approximately four months and a native-format archive of approximately 38 MB. Source listings were inspected during planning; download integrity and parsing remain implementation tasks.

Use a few contiguous weeks initially. Parse the individual dynamic matrices, not the topology's default aggregate peak matrix. Confirm dates, units, node IDs, direction, missing entries, and duplicate timestamps from the actual archive metadata. Build windows only within contiguous periods.

Extract the retained nodes' 8-by-8 matrices. Choose four to six active directed pairs using training-period information and path overlap, then freeze this selection. Preserve the complete extracted matrices for provenance, but mask inactive pairs in the experiment so no capacity is reserved for ungenerated traffic. Document that results concern selected trace-derived demands, not all-pair backbone traffic.

Start with a chronological training, validation, and test split, approximately 60/20/20 if sufficient contiguous data are available. Split before making sliding windows. Fit normalization and rate scaling using training data only. Forecast labels must not cross split boundaries.

Apply a shared traffic scaling factor to obtain meaningful load relative to configured capacity. Freeze the factor before final tests. Preserve temporal shape and pair ratios; do not tune each policy's offered load separately. Choose normal and congested load levels from training/validation observations, rather than selecting favorable test outcomes.

### European carbon data

Use ECON-PowerCI, a public country-level daily consumption-based electricity carbon intensity dataset for 35 European countries over 2015–2024. The Zenodo record provides an approximately 4.7 MB CSV download. No live API or account is required for this proposed input source.

Map each retained node to its actual country's data. Select carbon periods with complete coverage across all eight countries. Inspect the dataset's quality flags and retain them in metadata. Treat values as modeled country-level carbon intensity, not direct measurements of a router's electricity supply.

Use the consumption-based intensity field consistently. Its documented unit is kg CO2/MWh, numerically equivalent to g CO2/kWh. This source concerns CO2; do not silently label results CO2e or mix it with lifecycle or marginal-emissions datasets.

Daily carbon intensity stays constant across the 96 fifteen-minute traffic bins within a paired day. It changes only at daily boundaries in the primary experiment. Do not interpolate daily values into apparently observed subhourly fluctuations or claim intraday carbon forecasting.

### Geographic and temporal alignment

Geographic alignment is country-to-country: French nodes use French carbon data, German nodes use German data, and so on. The SNDlib traffic instance refers to 2005, while the carbon dataset starts in 2015; the inputs are not simultaneous observations.

Pair contiguous traffic days with contiguous carbon days using a documented weekday and season rule where possible. All countries must use the same carbon date for a given traffic day. Save both original timelines and the mapping in a manifest.

Describe the result as a constructed trace-driven scenario with geographically matched inputs. Weekday matching does not establish real traffic–carbon correlations. Train the GNN on traffic history rather than claiming that this pairing supports a learned joint traffic-and-carbon distribution.

For the paper, replay the same held-out traffic windows against at least three different complete carbon weeks. Report how much the conclusions depend on the pairing. Exclude incomplete periods according to a common rule before policy comparisons; do not invent replacement countries or primary synthetic carbon signals.

Historical daily averages are scenario inputs, not operational day-ahead forecasts. During simulation, reveal only the current scenario day's assigned carbon value and never future values to the planner. State that using a daily average throughout that day is a retrospective accounting abstraction, not a demonstrated live telemetry service.

## Architecture and module contracts

Use one repository. Pure Python modules communicate through function calls and typed data objects in the simulation; an HTTP service is unnecessary for the demo.

```text
GÉANT topology + selected historical demand + matched daily carbon
                              |
                              v
                     Causal replay engine
                              |
                 Past/current available observations
                              |
                              v
                   Small GCN plus GRU predictor
                              |
                 Forecast and validation error margin
                              |
                              v
                 Carbon and capacity aware planner
                              |
                         Route assignment
                              |
                              v
                Network load and service simulation
                              |
                              v
                 Logs, comparisons, demo visualization
```

Proposed modules, to create during implementation:

```text
contracts/      topology, snapshots, forecast and decision definitions
network/        subgraph, capacities, optional later Mininet adapter
prediction/     traffic windows, GNN, training, forecasting baselines
routing/        candidate paths, reservations, policy variants
simulation/     causal replay, load projection, service accounting
experiments/    scenario configuration and paired runs
analysis/       carbon accounting, metrics, plots
configs/        common experiment settings
inputs/         cached data and source manifests
artifacts/      checkpoints, scalers, model metadata
results/        generated logs and tables
```

Freeze these contracts early:

| Object | Required contents |
|---|---|
| Topology | Node order, original IDs, country mapping, directed links, capacities in Mbps, delays in ms, hash |
| Snapshot | Step ID, original traffic timestamp, mapped carbon date, available demand history, current routes |
| Forecast | Source step, horizon offsets, demand in Mbps, nonnegative margin, model ID, inference duration |
| Decision | Step ID, pair-to-path map, reason, projected maximum utilization, modeled path cost |
| Result | Policy, scenario, window, pairing, seeds, offered and served demand, load, routes, carbon, runtime |

Store arrays in NPZ and logs in CSV; use JSON for configuration and manifests. Validate shapes, units, finite values, masks, ordering, and graph hashes at boundaries.

## Causal replay and simulation fidelity

Use fifteen-minute scenario steps, independent of wall-clock speed. Decisions for bin k can use demand history through bin k-1. The predictive policy forecasts bin k onward; the reactive policy uses the last observed bin. Both policies decide before the replay engine reveals the actual demand in bin k. Then route the newly revealed demand using the committed assignment, record outcomes, and advance.

This is a one-bin observation/control abstraction, not a claim that a real controller needs fifteen minutes to install a rule. Explicitly disclose it. During the paper phase, vary observation and actuation delay, including an immediate-observation case where the reactive planner sees the current bin. This establishes whether any prediction advantage relies on delay assumptions.

The predictor and planner must never receive future traffic rows, future carbon rows, or test labels. Initial history may contain only rows before the selected evaluation window. Do not let the replay driver's access to the full file leak into the policy API.

The demo uses an aggregate rate model, not packet-level simulation:

- Offered link load is the sum of actual OD demand assigned through each directed link.
- Utilization is offered load divided by capacity.
- Overload metrics include time above capacity and integrated excess offered load.
- Compute feasible served rates using the same documented deterministic allocator for every policy. A progressive-filling allocator can share bottlenecks among active OD flows while respecting every link capacity and each flow's offered rate.
- Log offered and served rates separately. Unsatisfied demand is a modeled service deficit, not measured packet loss or TCP goodput.

Do not derive packet p95 RTT from demand bins. A later queue model must specify arrivals, buffering, service, and loss, and its delay remains simulated. Real packet RTT/goodput/loss belong to optional Mininet validation.

Virtual time can advance faster than real time. Run the simulation first, then animate saved route/load changes for presentation. Measure runtime during a pilot instead of promising a speedup in advance.

## Small GNN and conservative prediction

Use CPU PyTorch, NumPy, NetworkX, pandas, and Matplotlib. Avoid PyTorch Geometric extensions, DCRNN, Graph WaveNet, reinforcement learning, and architecture searches for the demo.

Represent switches as graph nodes. Node features contain the outgoing demand vector to the retained destination nodes. Use normalized adjacency with self-loops for a small graph convolution, a GRU for time history, and a nonnegative output head for three future demand matrices. Start around 32 hidden units and 12 past snapshots.

A snapshot represents fifteen minutes. Twelve historical snapshots represent three hours; three prediction horizons represent 15, 30, and 45 minutes. Mask diagonal and inactive demand pairs consistently in training, forecasting, and routing.

Forecast offered demand rather than policy-dependent link utilization. Project predicted demands onto candidate routes in the planner. Carbon and fixed delays are planner inputs; the GNN does not forecast grid carbon in this approach.

Select the checkpoint on validation demand MAE and compare with persistence and a plain GRU using comparable inputs. Report MAE by horizon and high-load errors; avoid MAPE near zero. Record training seed, node order, scaler, input hash, selected pairs, and checkpoint metadata.

Calculate a conservative margin from positive validation residuals, initially a pooled or per-horizon 90th percentile. Add that margin to the forecast when checking capacity. Validate the percentile and log held-out coverage. This empirical safeguard does not provide a formal SLO or uncertainty-coverage guarantee.

If simpler forecasting performs better, retain that result. Persistence is a comparison and component-removal experiment, not a replacement project or a substitute for the actual GNN in the demo.

## Routing policy

Precompute up to three loop-free candidate paths per active pair using the retained graph. Define delays explicitly; geographic distance may support an assumed propagation model, but source cost fields must not be misread as measured delay or installed capacity.

At each interval:

1. Project conservative demand over the forecast horizons onto the current route assignment.
2. Process pairs in a documented deterministic order, initially descending conservative demand.
3. For each candidate, remove the pair's old reservation and add the candidate reservation before checking link loads. Update reservations after accepting each change so multiple flows cannot all claim the same unused capacity.
4. Reject candidates above the configured propagation bound, initially 1.5 times shortest-path delay, or an initial 80% predicted utilization limit.
5. Among feasible candidates, select the smallest modeled forwarding carbon cost across all forwarding hops.
6. Require initially 5% cost improvement and a two-bin hold time for elective changes. Permit overload risk to override the hold time. Retain identical hysteresis machinery in the reactive comparator.
7. If no feasible candidate exists, choose the smallest projected maximum utilization and log infeasibility. Do not imply guaranteed latency or capacity compliance.

Freeze thresholds on validation data before final testing. This is greedy bounded candidate search, not a globally optimal multi-commodity solver. The simulation records route changes; it does not inherently model packet loss or reordering during updates.

## Carbon accounting

Primary environmental outputs are a carbon-weighted forwarding score and, if a defensible energy coefficient is established, modeled grams of CO2 per served decimal MB. Report served fraction alongside environmental results so dropping service cannot masquerade as efficiency.

For a forwarding coefficient epsilon in J/MB and intensity CI in g CO2/kWh:

```text
path intensity [g CO2/MB] = sum_over_forwarding_hops(epsilon_hop * CI_sender) / 3,600,000
forwarded MB in one bin = served_rate[Mbps] * 900[seconds] / 8
```

Use the original scenario duration for simulation accounting, not the shortened animation time. Count each directed forwarding hop once and define endpoint energy conventions. Carbon numerator and served-byte denominator must refer to the same serviced traffic and period. If no energy coefficient can be justified, keep the normalized score and do not invent absolute grams.

For sensitivity, separately model idle plus traffic-dependent power:

```text
P_i = P_idle_i + beta_i * served_load_i
modeled grams = sum_i,k P_i[W] * duration_k[seconds] * CI_i,k / 3,600,000
```

With all routers on, idle emissions are largely route-independent. Include an idle-dominated case and beta=0. Distinguish forwarding attribution from changes in total modeled emissions; neither is direct measurement of physical GÉANT electricity.

## Baselines and paper experiments

| Policy | Demand information | Objective |
|---|---|---|
| Shortest path | None | Fixed minimum configured propagation delay |
| Reactive carbon aware | Last observed demand | Carbon cost with current-observation capacity guards |
| Predictive traffic engineering | GNN forecast | Projected maximum utilization without a carbon term |
| Proposed predictive carbon aware | GNN forecast plus margin | Carbon cost with forecast-aware capacity guards |

Share candidates, capacity settings, initial routes, offered traffic, carbon inputs, timing, and update machinery. Reactive and predictive carbon modes share delay limits, capacity thresholds, and hysteresis; document the intended forecasting/margin differences.

Required component comparisons: persistence instead of GNN, plain-GRU forecast accuracy, proposed policy without the error margin, and proposed policy without hysteresis. All remain experiments within this approach.

Primary scenarios use held-out trace windows at predefined normal and congested load levels. Add a noisy-burst scenario by explicitly perturbing trace demands with seeded bursts; label it modified trace traffic. Include periods with modest carbon contrast rather than selecting only unusually large differences.

For Wednesday: complete a pilot for each main policy, a clear route-change demonstration, and an initial comparison with the margin removed. Use held-out inputs and saved logs.

For the paper: aim for at least five distinct held-out windows or workload realizations, three carbon-week pairings, and normal/congested/perturbed load conditions. Pair each exact realization across policies. A repeated deterministic run with a new seed label is not a new workload. Use run/window-level uncertainty and paired differences; do not treat correlated bins as independent samples.

Report demand MAE, maximum/p95 link utilization, overload duration and excess-load integral, served-demand fraction, forwarding carbon score or justified modeled CO2/MB, route-change count, and compute overhead. The p95 here concerns utilization, not packet latency. Add actual packet metrics only after Mininet validation.

Produce forecast-error plots, link-utilization timelines, carbon versus overload/service tradeoffs, and route-change/component-comparison plots. Include unfavorable outcomes and record failed runs. Keep all initial-history exclusions identical across policies.

## Team modules and Windows workflow

| Owner | Workstream | Deliverables |
|---|---|---|
| Ashutosh | Prediction and integration | Demand loader, small GNN, checkpoint/scaler, forecast comparisons, routing integration |
| Tanay | Network and simulation | Exact subgraph, capacity/delay config, causal replay, load/service engine, optional later Mininet adapter |
| Avaneesh | Carbon and evaluation | Country carbon loader, timestamp pairing, accounting, paired experiments, figures and methodology |

Assignments may be swapped for interest. One owner edits shared contracts/configuration at a time. Integrate a real replay from loader to planner to result log by Day 2, initially using persistence as a development fixture. Replace that fixture through the same interface with the trained GNN before the demonstration.

Use one shared Git repository and small daily merges. Branch names can use codex/prediction, codex/simulation, and codex/evaluation. Share input manifests, configuration, and checkpoints; recreate environments from pinned dependency files rather than copy virtual environments between laptops.

Both laptops use native Windows Python for the demo. The 8 GB machine can handle small data processing, model checks, planner work, and figures; stream the source archive and avoid loading unnecessary matrices. Run larger training/experiment batches on the 24 GB machine as needed. A GPU, Linux VM, and remote inference service are not required for the simulation.

I can perform implementation when requested. Team members validate their outputs and understand their modules for the viva. Keep a short daily integration check; automate training, experiment batches, figure generation, and startup to reduce manual effort.

The reproduction package contains the source revision, dependency lock, configuration, input hashes, chronological splits, country/date mappings, checkpoint/scaler, selected pairs, run definitions, and logs. Cold-start it on the friend's Windows laptop before the demo. Results generation must not require a network connection.

## October 14 demonstration schedule

| Date | Work | Completion gate |
|---|---|---|
| Oct 8 | Confirm subgraph and data sources; freeze units and contracts | Exact eleven-link graph and agreed input schemas |
| Oct 9 | Parse/cache traffic and carbon; implement causal replay and first baseline | One real-data replay writes valid load and carbon logs |
| Oct 10 | Train small GNN; implement policy variants and validation margin | Held-out MAE comparison and compatible checkpoint |
| Oct 11 | Integrate GNN, reservations, service allocator, and hysteresis | All four policies run against identical inputs |
| Oct 12 | Paired pilot and margin comparison; check alignment/leakage | Reproducible preliminary results and frozen demo configuration |
| Oct 13 | Figures, network animation, explanation and rehearsal | Saved demo run plus cold-start reproduction on the integration laptop |
| Oct 14 | Working simulation demo and module explanations | Offline demonstration from real cached data and trained GNN |

No model-architecture changes or added topologies after configuration freeze unless a correctness issue requires them. Rerun affected comparisons after changes. A demo recording may preserve the current simulation's presentation; it is not an archived older project approach.

## Optional Mininet validation during the paper phase

Reuse this exact graph, selected demands, country data, checkpoint interface, and routing policies. One node becomes one Open vSwitch; attach hosts for selected endpoints. Each original link becomes a shaped virtual link. A traffic driver converts demand bins to iperf rates and a controller installs the chosen OpenFlow paths.

Use one Linux VM on the 24 GB Windows laptop only for this extension, initially around 4 vCPUs and 8 GB RAM if the host can spare them. Mininet's packaged VM is a starting option, not proof of controller compatibility. Do not require every team member to install it.

Validate controller, OVS, namespace, shaping, and forwarding behavior before expanding the topology. Ryu is unmaintained; evaluate and pin a working controller stack if this extension is attempted. OS-Ken 4.0 removed its standalone launcher, so a latest-version installation cannot be assumed to work as a drop-in standalone controller. Report the actual controller used.

Run inference in a separate process for the controller extension. No packet event handler waits synchronously for inference. Apply decisions with version/timestamp checks and bounded queues; handle missing predictions without erasing valid routes. Use static ARP and pair-specific forwarding for the initial extension to limit broadcast-loop problems.

Replay a fifteen-minute traffic bin over an initial 30 seconds, recording original and wall-clock times. Forecast horizons of one to three bins then represent 30, 60, and 90 replay seconds. Declare capacity/rate scaling and do not imply accelerated packet behavior exactly reproduces a production WAN. Use wall-clock duration for the actual emulation's modeled energy; label any reconstructed scenario-duration totals separately.

Measure receiver goodput, loss, RTT, inference/controller overhead, and update transients. Keep post-reroute intervals in primary results. Explain that Mininet emulates actual packet forwarding while the Windows simulator calculates aggregate behavior. Neither requires live carbon APIs.

If this extension is not completed, finish the paper with clearly stated simulation evidence and do not claim measured packet performance or OpenFlow-actuated validation.

## Verification and evidence limits

Required checks: exact retained nodes/links; node ordering and country mapping; dynamic rather than aggregate traffic input; timestamp continuity; masks and units; chronological split boundaries; no future access; shared baseline inputs; removal of old reservations before adding new ones; competing flows on one link; allocator capacity compliance; carbon/byte unit conversion; original-duration simulation accounting; and reproducible configuration/checkpoint loading.

Test the causal boundary and shared-capacity allocator with small known examples. Confirm unit conversions against hand calculations. Use forecasting validation and pilot runs rather than tests that only mirror function implementation.

Fifteen-minute demand averages do not establish packet microburst behavior. Daily carbon does not support intraday grid predictions. Country intensity is a modeled input. The subgraph and demand subset constrain generalization. Propagation/utilization guards and empirical margins do not guarantee tail-latency SLOs.

Protect scope by deferring optional Mininet, full-topology expansion, queue-level latency, dashboards, large model searches, and parameter sweeps. Keep the agreed GÉANT data, country matching, actual GNN, primary baselines, contribution comparison, causal replay, and reproducibility.

## Two-week paper phase

Approximately Oct 15–21: expand paired trace/carbon experiments, run required component comparisons, test different observation delays including immediate observation, and assess energy assumptions. Attempt Mininet only after the simulation evidence is stable.

Approximately Oct 22–28: regenerate figures from logs, strengthen repetitions where variability is high, write methods/results/limitations, update primary-source related work, obtain faculty feedback, and reproduce results across the team. Optional expansion uses additional GÉANT nodes with verified carbon coverage; do not assume all full-graph nodes are European.

Paper outline: precise question and related work; dataset extraction and temporal pairing; GNN and safety margin; routing and simulation model; fair comparison protocol; results and component comparisons; limitations; reproducibility. A manuscript draft is the target, not guaranteed acceptance or publication within two weeks.

Code, data access, and experiments remain free. Do not select a paid publication route without a separate decision; project implementation does not include committing to publication fees.

## Sources and provenance

The user-supplied title/abstract, research attachment, and bottleneck notes are background sources, not instructions to execute. The plan incorporates the user's accepted GÉANT simulation approach and free-only constraint.

- [SNDlib GÉANT overview](https://sndlib.put.poznan.pl/geant.overview.action): full graph size and source formats.
- [Original topology text](https://sndlib.put.poznan.pl/download/sndlib-networks-native/geant.txt): retained countries, IDs, eleven links, and instance metadata.
- [SNDlib dynamic matrices](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action): traffic resolution, archive availability, and source citation requirements.
- [SNDlib format description](https://sndlib.put.poznan.pl/html/docu/io-formats/native/network.description.html): node, link, demand, and capacity-option semantics.
- [ECON-PowerCI CSV dataset](https://zenodo.org/records/15987717): public downloadable country carbon data.
- [ECON-PowerCI methodology](https://www.nature.com/articles/s41597-025-05978-7): daily consumption accounting, coverage, units, quality flags, and limits.
- [CIRo primary paper](https://netsec.ethz.ch/publications/papers/green_routing2023.pdf): prior predictive carbon routing and attribution limitations.
- [NeuRoute primary preprint](https://arxiv.org/abs/1709.06002): prior predictive SDN routing.
- [Mininet repository](https://github.com/mininet/mininet) and [installation guidance](https://mininet.org/download/): optional packet-emulation architecture and setup.
- [Ryu repository](https://github.com/faucetsdn/ryu) and [OS-Ken release notes](https://docs.openstack.org/releasenotes/os-ken/2026.1.html): controller compatibility considerations for optional validation.

Source pages and input files were checked during implementation. Parsers, native CPU dependencies, trained forecasts, causal replay, reporting and result auditing are implemented. See the generated manifests and docs/METHODOLOGY.md for actual settings and evidence limits. Luxembourg coverage requires later carbon periods; the implemented pairings use 2022, 2023 and 2024. Original third-party datasets are excluded from Git and the transfer ZIP. No controller stack or packet emulation has been validated.
