# Five-minute demo and viva guide

1. Open `DEMO.html` or run `RUN_DEMO.ps1`. No internet is needed for the saved report. Explain that there are eight real GÉANT nodes and eleven retained links, with experimental capacities.
2. Keep **Congested / 1 bin / GNN + safeguards** selected. Choose a flow, press **Play**, and show its route and offered versus served rates. The blue line is that flow's path, not all traffic. Link labels show the worse of the two directions; hover for both.
3. Switch to **Reactive carbon**, then **Shortest path**. The workload and carbon inputs remain the same. Explain that lower carbon score must be read alongside service and overload. Top cards refer to the displayed day; the table averages the selected campaign cases.
4. Show **GNN without margin** and **Persistence + safeguards**. Describe the contribution honestly: forecasting plus conservative shared reservations and route-change control are being tested as a combination.
5. Show the forecast table. State that the first run does not establish the GNN as a better forecaster. Open `results/paper/index.html` to inspect 495 runs, including unexpected bursts and immediate observations. Finish with the actual trade-off and limitations.

## Explain in ordinary language

- **SDN:** a central routing application chooses paths using a view of the network. Here we simulate its decision loop; we do not send OpenFlow messages to switches.
- **GNN:** each node combines its outgoing-demand features with its neighboring nodes' features. A GRU then learns changes over the preceding three hours.
- **Forecast margin:** add an allowance based on past validation underpredictions before deciding whether a path has room.
- **Reservation:** when checking a new path, subtract the flow's old planned load first, then reserve the new path immediately. This prevents several flows claiming the same spare capacity.
- **Hysteresis:** wait between elective changes and require a worthwhile benefit. Bypass that wait when the current path is forecast to become unsafe.
- **Carbon:** a route is charged for the national electricity intensity of its forwarding nodes. This is a modeled forwarding score, not measured CO2 savings.
- **Why the dates differ:** topology and traffic are historical; country carbon series come from later years. Country/weekday/season pairing creates a controlled hypothetical experiment.

## Honest answers to likely questions

**Where is Ryu?** Ryu is an SDN controller framework. The accepted scope uses a lightweight simulator of centralized routing, so no controller installation is required. Actual switch actuation is an optional future extension.

**Why not the whole GÉANT?** A retained subgraph makes training and controlled comparisons small enough for a laptop. It limits generalization; the paper must state the topology and selected demand subset.

**Does it reduce real energy?** That was not measured. Routing changes a forwarding attribution score; all-on idle equipment can dominate energy and remain unchanged. The beta=0 sensitivity makes this explicit.

**Why is the GNN not always best?** Stable traces favor persistence, abrupt changes are hard to predict, and a small graph may add little signal. The experiment must separate the model from the safeguards instead of claiming success from one favorable example.

**What is novel?** The testable modification is the combination and evaluation of validation-calibrated reservations with carbon path choice and hysteresis. The broad ingredients already exist. Novelty approval and publication require a careful related-work comparison and faculty review.

## Optional Mininet work remains separate

Reuse the graph, demand mask, trained model and routing interface in a Linux VM on the stronger laptop. Add switch/host creation, shaped links, a pinned working controller, pair-specific rules, traffic replay and packet measurement. That extension is not installed, implemented or validated by this native Windows build. Do not claim measured RTT/goodput or working OpenFlow until it is actually run.
