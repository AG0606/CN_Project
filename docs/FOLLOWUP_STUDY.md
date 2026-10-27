# Later-period training and routing follow-up

This follow-up tests the frozen joint planner on later source periods and evaluates actual new training, without changing the original reference models. The locally saved [protocol](../configs/followup_protocol.json) was recorded before the later test outcomes were evaluated. It is not an external preregistration. "Later test" means these periods were not used in the project's recorded earlier routing evaluations; the original archives had already been downloaded and parsed.

The completed results are written to [`results/followup-study-20261027/FINDINGS.md`](../results/followup-study-20261027/FINDINGS.md), with every declared method in the CSVs. At the team's request, this training-comparison section is no longer displayed on the main dashboard; the research record and negative results remain available here.

## Chronological data and fairness

| Network | Expanded training history | Later validation | Final test source period | Routing replay dates |
| --- | --- | --- | --- | --- |
| GÉANT | Original 42 calendar days, 4 May–14 June 2005 | 15–28 June 2005 | 29 June–12 July 2005 | First seven complete days: 30 June–6 July |
| Abilene | X01–X04: four original source weeks | X05: 22–28 April 2004 | X06–X07: 1–14 May 2004 | First seven complete days: 2–8 May |

Earlier pilot validation and test rows can now be part of expanded training. They are never presented as a new test. Missing timestamps and gaps between Abilene weeks are not interpolated or crossed by forecasting windows. The original six selected OD pairs, capacity assumptions, traffic scaling factor, and training-only normalization are fixed across all variants. More training data does not mean changing test traffic to favor a policy.

Final forecast metrics use all contiguous windows inside the declared final test split. The routing comparison uses seven complete days with history and three-horizon labels contained inside that split. Each day has the same normal, congested and seeded-burst workload for every policy. GÉANT uses the fixed 2022 daily country-carbon pairing; Abilene uses fixed 2004 annual EPA rates. No paid API or synthetic hourly carbon series is used.

## Training comparisons

- **Reference:** the existing trained GNN and matched GRU, plus the original persistence calibration.
- **Longer:** the original training and validation splits, up to 100 epochs with patience 12. Early stopping chooses the checkpoint using original validation OD MAE.
- **Expanded:** more real training history and the later validation period above, with the same architecture and up to 100 epochs/patience 12.
- **Link-load loss:** the same expanded history and architecture, with a fixed 0.25-weighted shared-link prediction error term added to OD MAE. Both GNN and matched GRU get the same modified loss.
- **Recalibrated persistence:** repeat the last observed matrix, with its uncertainty margin calibrated on the same later validation data used by expanded models.

The extra loss projects OD prediction errors onto the original shortest-path link incidence matrix. Errors that accumulate on a shared link therefore affect training together. The link-error weight is `1 + min(actual training/validation link utilization, 2)`. This is a link-load proxy loss, not differentiable optimization through the final routing algorithm. Actual test targets never enter training, margin calibration, checkpoint selection, or loss weights.

The training code has an explicit `evaluate_test=False` mode, covered by a test that fails if the routine requests test windows. Both ordinary validation MAE and selection loss are logged, because the link-loss selection objective is different. Original checkpoints remain under `artifacts/` and `artifacts/abilene/`; new checkpoints are under `artifacts/followup/{network}/{variant}/`.

## Routing and audit

All new forecasts use the same zero-budget `TradeoffPlanner`, congestion weight 1.0, per-flow switching penalty 0.005, 80% planning guard, and one-bin observation delay. Reactive carbon, shortest path, the original guarded GNN policy, and the explicitly clairvoyant current-bin oracle are retained. There are 15 declared cases per day/workload and 630 total routing runs. The planner's constraints operate on forecasts; observed service and overload can still worsen.

Before the first final forecast or routing outcome is computed, `evaluation_plan.json` freezes the protocol, scientific source hashes, traffic and carbon source hashes, model/checkpoint hashes, environment versions and test-day list. Resuming is permitted only when the plan matches; completed evaluations are reused after checksum verification. Do not tune on these results and label the rerun an independent test.

```powershell
.\.venv\Scripts\python.exe -m carbonroute.followup all
# Or resume a single stage: prepare / train / evaluate / report
.\.venv\Scripts\python.exe scripts/verify_followup.py results/followup-study-20261027
.\.venv\Scripts\python.exe scripts/audit_followup_data.py results/followup-study-20261027
.\.venv\Scripts\python.exe -m carbonroute.abilene report
.\.venv\Scripts\python.exe scripts/build_dataset_showcase.py
```

The auditor checks paired input equality, accounting, observation timing, predicted guard records, frozen hashes, chronological split separation and training artifacts containing only validation metrics. Original source bytes and full per-bin logs are local and ignored by Git; metadata, model artifacts and aggregate evidence are shareable. The dataset showcase includes X05–X07 and separate follow-up processed arrays.

One training seed, seven adjacent routing days per network, coarse carbon signals, selected flows and assumed capacities limit the findings. Carbon remains a forwarding attribution proxy, not measured CO₂. The contribution under investigation is a tested combination of link-load-aware forecasting and guarded joint carbon routing; a GNN-specific advantage must be demonstrated against the matched GRU and persistence, rather than assumed.

## Completed outcomes and source audit

All 12 new neural checkpoints were trained and all 630 routing runs completed. The integrity audit passes. Longer training, expanded history and the link-load loss did **not** consistently improve final forecast MAE. Across three horizons, the GÉANT original GNN averages 1.12534 Mbps MAE versus 1.17813 expanded and 1.21982 link loss; Abilene averages 0.34969 original versus 0.38946 expanded and 0.38129 link loss. Retain these negative results.

On Abilene's congested workload, reactive carbon averages score 1956.84 and 177.14 overload minutes/day. The joint planner with the original GNN reaches 1921.79 and 173.57 minutes; with link-loss GNN, 1915.61 and 175.00 minutes. That is a modest carbon-proxy improvement with mixed overload behavior, not evidence that extra training generally improves forecasts or routing. Compare GRU, persistence and route changes before attributing an improvement to the GNN.

The post-evaluation audit found **three GÉANT replay days with no listed native demands**: 30 June, 1 July and 2 July. Another replay day, 3 July, has 43 empty fifteen-minute source sections out of 96. The full forecast test split additionally includes the empty 29 June. The parser's declared rule treats unlisted demands as zero; the archive does not establish actual zero network traffic or the cause of these empty sections. They remain in all saved logs. Fully empty days have undefined carbon scores, never zero. GÉANT carbon means therefore have only four defined days (including partially empty 3 July); the saved report explicitly shows that count. The unchanged assumed capacities also severely saturate the populated later days. This makes the later GÉANT experiment a limited stress test, not a clean confirmation of practical savings.

The follow-up report pools served bytes over offered bytes across all seven days. It does not average the simulation's 100% service convention for an empty day into a purported overall service rate. Other daily metrics still average all seven days, so their denominators are explicit. The frozen `day_cluster_intervals.csv` has undefined GÉANT carbon differences/intervals because empty-day NaNs propagated; its seven-cluster count includes empty days. Those rows support no GÉANT carbon confidence claim. The post-evaluation `source_availability.csv` and `data_quality_audit.json` document the source issue without changing any frozen scientific inputs or outputs.

For a future confirmation, establish source-availability criteria and capacity scenarios before evaluating a **new** period. Do not replace unfavorable or empty days from this completed test and call the replacement an independent result. More seeds and better capacity-regime coverage remain future work; no second tuning pass was performed after reading these outcomes.
