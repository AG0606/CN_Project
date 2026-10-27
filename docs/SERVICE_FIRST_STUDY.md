# Service-first carbon-aware routing

This study tests a service-first joint planner using the existing single-path candidate routes and original trained GNN or persistence forecast. It is a separate experiment from the locally frozen [earlier training follow-up](FOLLOWUP_STUDY.md). The [results and full tables](../results/service-first-20261027/FINDINGS.md) include all eight methods; the combined offline dashboard has a new service-first section. The earlier training-comparison panel was removed from the dashboard at the team's request; its evidence remains intact.

## Method

For each candidate assignment and forecast horizon, apply the same equal-rate max-min allocator used for realized service. Maximize total predicted served demand across horizons. Keep assignments whose predicted served amount is within **0.1% of total predicted offered demand** of that maximum. From those, minimize predicted served-byte carbon score, breaking ties by changed routes, modeled delay and deterministic assignment order. It considers only observed history and the selected prediction with its original validation margin. It makes one assignment for all horizons before actual current traffic is revealed. This design can trade some service for a lower predicted score; forecast error, service fairness and actual outcomes are not guaranteed.

The fixed 0.1% tolerance is a design choice declared before the later-period runs, not a tuned optimum. Candidate paths still satisfy the existing stretch settings. The carbon score is a modeled forwarding attribution, not measured electricity or physical emissions. The modeled path delay is a propagation/router proxy, not packet RTT. The GNN and persistence are existing models; no new neural training occurred in this study.

`src/carbonroute/service_first.py` implements the planner and a batched version of `progressive_fill`; a test compares its output to the original allocator. `service_first_simulation.py` is a separate replay module, retaining the original simulation source unchanged so the earlier study's recorded source hashes remain valid. `service_first_experiment.py` defines the paired campaign, and `configs/service_first_protocol.json` records the fixed method and dates. Every policy has the same network, traffic, candidate paths, carbon and capacities; the current-bin oracle is explicitly clairvoyant and diagnostic only.

## Dataset and results

The seven later GÉANT replay days are 14–20 July 2005, paired with 2022 daily country intensity. All native demand sections for those days and the initial lookback are nonempty; this does **not** establish that the original source is complete or error-free. GÉANT's assumed capacities still cause severe saturation: the congested reactive baseline serves only 19.69% of offered bytes, so treat that period as a stress test rather than a representative operational result. Abilene uses 16–22 May 2004 traffic and fixed annual EPA regional rates for 2004. Workloads include normal, a fixed 1.6× scaling and seeded bursts; scaling and capacities are simulation assumptions.

On the congested Abilene workload, reactive carbon averages score 2014.53, pooled service 99.75%, and 57.86 overload minutes/day. Service-first GNN reaches score 1898.73, pooled service 99.87%, and 36.43 overload minutes/day, but route changes rise from 27.14 to 53.86/day. The existing joint GNN reaches score 1971.31 and 22.86 overload minutes/day: service-first improves score against that planner but has more overload. Service-first persistence gets score 1899.61 and 34.29 overload minutes/day, so no distinct GNN advantage is established. The other workloads and GÉANT show mixed results; retain all runs rather than presenting only the favorable case.

These are comparisons on the new dates, **not direct before/after differences across different date ranges**. Seven adjacent days, one training seed, repeated comparisons, assumed capacities and a served-byte-normalized carbon score limit statistical and operational claims. Per-pair service and total served bytes must accompany carbon scores. Bootstrap intervals are descriptive with few adjacent clusters.

## Reproduce and verify

```powershell
.\.venv\Scripts\python.exe -m carbonroute.service_first_experiment
.\.venv\Scripts\python.exe scripts/verify_service_first.py results/service-first-20261027
.\.venv\Scripts\python.exe scripts/report_service_first.py results/service-first-20261027
.\.venv\Scripts\python.exe -m carbonroute.abilene report
.\.venv\Scripts\python.exe -m pytest -q
```

The protocol and hashes are recorded before outcome evaluation; on resume, changed inputs, models or scientific code are rejected. Original data and detailed per-bin logs are local and ignored by Git. A saved dashboard includes aggregate results. A new experimental policy or test protocol needs a new output folder; do not change these recorded results or tune on the final test and call the rerun independent. Full replay logs are required for the independent auditor and can be regenerated from the verified free inputs.
