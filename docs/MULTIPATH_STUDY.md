# Fractional multipath carbon-aware routing

This extension routes an OD traffic aggregate over several candidate paths simultaneously, using a free SciPy/HiGHS linear optimizer. It is a trace-driven fluid simulation. It does not demonstrate packet-level ordering, flow hashing, installation of OpenFlow rules or measured carbon emissions. Existing neural models are reused; no additional model training occurs here.

## Implementation and contracts

`src/carbonroute/multipath.py` contains the path representation, LP planner, 100-bucket quantization, and per-OD fluid allocator. `multipath_simulation.py` commits fractions before target demand is revealed and records offered/served rates per OD, path and link. `multipath_experiment.py` freezes the protocol, scientific sources, raw/prepared inputs, model hashes and environment before outcome evaluation. Reporting and verification live in `scripts/report_multipath.py` and `scripts/verify_multipath.py`; the main two-tab dashboard has a separate comparison section.

The candidate paths and delay stretch are the same as for the single-path algorithms. The LP constrains every OD's path fractions to sum to one: all offered traffic is assigned to paths, including traffic that will exceed capacity. Thus reduced throughput cannot masquerade as reduced offered overload. The actual service allocator applies equal-rate max-min fairness to each entire OD aggregate; its multiple subpaths do not gain multiple fairness shares. One-hot path fractions exactly match the old single-path service model, checked both by tests and at replay time. The other algorithms, source inputs and earlier frozen studies remain separate and unchanged.

## Fixed optimization rule

The per-OD maximum across the three forecast horizons forms a conservative planning envelope. Stage 1 minimizes maximum offered link utilization while conserving each OD over candidate paths. Carbon mode then minimizes mean forecast offered demand times path carbon, subject to a peak limit of `max(0.8, minimum achievable envelope peak)`. TE mode holds the minimum peak and has no carbon objective. The difference is explicit: carbon mode can spend unused capacity up to the standard 80% planning guard to prefer cleaner paths; TE pursues minimum utilization. A final LP minimizes the L1 change in fractions while preserving previous objectives within numerical tolerances. Unsuccessful LPs fail visibly; no synthetic success is substituted.

The GNN and persistence variants use their original validation margins, while the reactive variant repeats the last observation without a margin. Ratios are fixed before the actual current bin arrives; actual demand then enters the common allocator. The optimization objective uses offered demand, whereas the dashboard carbon score is served-byte normalized. Lower score can therefore coexist with lower service or a different served mix and must be interpreted with the service and fairness columns.

The finite-weight variant rounds using the largest-remainder rule to 100 buckets per OD. All OD fractions still sum to one. Rounding may violate the predicted planning guard; those events are counted rather than hidden. The ideal fractional and rounded results do not establish practical per-flow splitting accuracy or packet-order preservation.

## Protocol and source preflight

The initial proposed GÉANT period, 22–28 July 2005, failed the nonempty-native-section rule with 132 unavailable bins. It produced no routing outcomes. Its frozen protocol, failure note and source-only availability screen are retained under `results/multipath-20261027/`. The first seven-consecutive-day period on/after 22 July with nonempty native sections and the initial three-hour lookback begins **26 July**. This selection used only source availability, not traffic magnitude, carbon, or routing performance. The version-2 protocol is stored in `configs/multipath_protocol.json` and copied to the completed output before routing. Nonempty source sections do not guarantee complete measurements; the original zero rule for individual unlisted OD pairs is retained and disclosed.

The primary output is `results/multipath-20261027-v2/`. GÉANT replay dates are **26 July–1 August 2005**, with daily 2022 country carbon. Abilene replay dates are **24–30 May 2004**, with fixed annual 2004 EPA regional rates. New dates do not overlap the recorded previous routing tests. The source archives had already been downloaded; this is fresh relative to earlier recorded routing outcomes, not an external preregistration.

All eleven policies are retained for each of seven days, three workloads and two networks: **462 runs**. Comparisons include shortest path, reactive carbon, existing joint GNN, single-path service-first GNN and persistence, equal splitting, multipath TE without carbon, carbon multipath with GNN/persistence/reactive demand, and 100-bucket GNN splitting. The six training-selected OD pairs, training-only scaling and normalization, static assumed capacities, one-bin lag and workload seeds are identical for all methods within a paired case. Absolute results from different date ranges are not direct before/after comparisons.

## Reproduction and evidence

```powershell
.\.venv\Scripts\python.exe -m carbonroute.multipath_experiment
.\.venv\Scripts\python.exe scripts/verify_multipath.py results/multipath-20261027-v2
.\.venv\Scripts\python.exe scripts/report_multipath.py results/multipath-20261027-v2
.\.venv\Scripts\python.exe -m carbonroute.abilene report
.\.venv\Scripts\python.exe scripts/build_dataset_showcase.py
# Optional: reproduce the availability-only screen in a new empty folder
.\.venv\Scripts\python.exe scripts/screen_source_availability.py --output results/my-source-screen
```

SciPy 1.18.1 is pinned in the project dependencies and Windows lock file; it requires Python 3.12 or newer, matching the existing Windows setup's tested Python 3.12. The package minimum is now 3.12. Its HiGHS solver needs no paid service or API key. Full per-bin logs and raw data are local and ignored by Git. Aggregate CSVs, immutable protocol/evaluation metadata, the audit result and findings are shareable. Resuming a completed study reuses checksum-verified evidence and rejects changes in scientific sources, inputs, models or the recorded environment.

The auditor reconstructs source workloads and carbon, verifies shared paired inputs, checks causal observation timing, conserves traffic across OD/path/link rates, enforces link capacity, independently certifies per-OD max-min allocation, and recalculates carbon and summary metrics. Unit tests verify a disjoint-path throughput gain, the impossibility of bypassing a shared cut, no extra subpath fairness, one-hot equivalence, carbon choice, quantization and causality.

## Interpretation

The completed audit verifies **462 runs and 88,704 intervals**, including source pairing, full-offered overload and per-OD fairness certificates. On the GÉANT normal workload, reactive carbon serves 50.581% of bytes with score 596.24 and 675 overload minutes/day. Carbon-aware GNN multipath serves 56.961%, score 571.10 and 546.43 overload minutes/day. However, fixed equal splitting serves more (61.819%) with a higher score (612.90), so the learned/carbon method does not dominate the simple control. The strongly saturated assumed-capacity regime still limits interpretation.

On congested Abilene, carbon-aware GNN multipath lowers score from reactive 1926.00 to 1910.36, but pooled service drops from 96.508% to 95.942% and worst-pair service also falls. The existing single-path service-first GNN has a lower score (1896.05) and higher pooled service (96.486%) than carbon multipath, though slightly more overload. Bursty and normal cases show other tradeoffs; all are retained. GNN and persistence multipath remain very close. Descriptive carbon intervals on the congested workload span zero for both networks. These observations do not establish a consistent or statistically strong advantage from the new method.

Read the generated [findings](../results/multipath-20261027-v2/FINDINGS.md) for all results. Report pooled byte service and worst-pair service with the carbon proxy; a lower normalized carbon score alone is insufficient. Changed OD pairs and redistributed fraction mass describe different aspects of reconfiguration and should be read together. The forecast horizon envelope and fixed margins can be overly conservative under distribution shift. Fractional splitting does not increase physical cut capacity, so severe saturation can remain.

Seven adjacent days per network, one existing neural seed, selected flows, coarse carbon signals, assumed capacities and simulated workloads limit generalization. Day-bootstrap intervals are descriptive; served-fraction intervals concern daily fractions rather than pooled-byte percentages. Compare against matched persistence, no-carbon and equal-split controls before claiming a GNN or carbon-specific advantage. Multipath and traffic engineering are established methods; any research contribution must concern the tested carbon/service combination or a reproducible empirical finding, rather than claiming that traffic splitting itself is new.
