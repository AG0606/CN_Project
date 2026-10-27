# Exploratory joint routing and oracle study

This implements the first phase of the follow-up requested after the GÉANT and Abilene pilots. It uses the existing trained checkpoints and prepared historical inputs. **It does not retrain the models.** The two validation days per network were already used during development; these results are exploratory and are not an independent final test. The predicted peak guard was added after inspecting an earlier validation run, so the final policy itself was informed by the validation data.

The two-tab [dashboard](../results/demo/index.html) includes a new **New planner: exploratory validation** table. Its workload follows the dashboard workload selection; these rows come from this study, not from the original held-out replay shown above it. GÉANT uses the 2022 country-carbon pairing for 2005 traffic; Abilene uses fixed 2004 annual EPA subregion rates. This is an aggregate simulation, not measured emissions, packet latency, or an installed SDN controller.

## Decision rule

`TradeoffPlanner` enumerates the same delay-bounded candidate path assignments used by the existing joint planner: 64 for the selected GÉANT flows and 324 for Abilene. A separately updated reactive-carbon planner sees the same past history as the other methods. For each assignment, its carbon cost and maximum link utilization over three horizons are calculated using the **same forecast** as for the reactive assignment. GNN, GRU, and persistence variants use their existing validation-derived margins; the observed-traffic variant repeats the last observation without a margin.

An assignment is eligible if its predicted carbon cost is within the reactive assignment's predicted cost plus a budget fraction (0% or 2%), and its predicted peak utilization is no greater than the larger of the configured 80% planning guard and the reference assignment's predicted peak. Among eligible assignments, the planner minimizes:

```text
predicted carbon cost / reference carbon cost
  + 1.0 × max(0, predicted peak utilization - 0.80)
  + 0.005 × number of changed flow routes
```

The reference assignment is always eligible, including when the reference itself exceeds the planning guard. The guards and score use **predictions**, not the actual next demand; they do not guarantee actual service, overload or the served-byte carbon score. The switching penalty is an experimental objective term, not a measured operational switching cost. There is no trained confidence gate or formal probability guarantee in this implementation.

The `oracle_current_bin` is deliberately clairvoyant: it sees the actual current demand and chooses the lowest offered-demand-weighted carbon assignment that keeps every offered link within capacity. If none exists, it minimizes peak utilization first. It ignores switching cost and does not see future bins. Because it optimizes offered-demand cost while the reported score is weighted by **served** bytes, and because it acts one bin at a time, it is a useful headroom diagnostic, **not a guaranteed lower bound on the reported daily score**.

## Results on validation data

Means in this table are over two validation days for each workload, using the **0%** budget and GNN forecasts. They are paired against reactive carbon on the same traffic and carbon inputs. Carbon score is an attribution proxy, not grams of CO₂.

| Network / workload | Reactive score | New GNN score | Reactive overload min/day | New overload min/day | Reactive served | New served | Route changes: reactive → new |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GÉANT normal | 462.92 | 462.62 | 0.0 | 0.0 | 100.00% | 100.00% | 15 → 15 |
| GÉANT congested | 524.67 | 499.74 | 82.5 | 90.0 | 98.22% | 98.08% | 18 → 27 |
| GÉANT bursty | 490.40 | 483.11 | 97.5 | 97.5 | 97.93% | 97.93% | 24 → 28 |
| Abilene normal | 1967.73 | 1953.44 | 0.0 | 0.0 | ~100% | ~100% | 1 → 2 |
| Abilene congested | 1984.56 | 1968.08 | 0.0 | 0.0 | ~100% | ~100% | 9 → 10.5 |
| Abilene bursty | 2043.90 | 2004.84 | 15.0 | 12.5 | 99.89% | 99.91% | 27 → 31.5 |

The carbon score is lower in these six validation comparisons, but GÉANT congested loses service, has more overload, and changes routes more often. The GNN and persistence variants produce **identical Abilene outcomes** for these three workloads at the reported precision; GÉANT outcomes are close. Therefore this does not establish a GNN advantage. The 2% budget produced only small differences here, and did not remove the GÉANT congested overload trade-off.

As an illustration of potential headroom, the clairvoyant current-bin oracle on the two congested GÉANT validation days produced score 481.71 and 75 overload minutes/day, versus reactive 524.67 and 82.5. On the Abilene bursty validation days, it produced score 1983.70 and zero overload minutes, versus reactive 2043.90 and 15. These are diagnostic comparisons with future information and without the planner's switching penalty; they are not achievable-performance claims.

## Reproduction and audit

```powershell
.\.venv\Scripts\python.exe -m carbonroute.tradeoff_experiment --output results/my-tradeoff-validation
.\.venv\Scripts\python.exe scripts/verify_tradeoff.py results/my-tradeoff-validation
```

The saved study has 156 runs: two networks × two days × three workloads × 13 policies/budget cases. The [summary](../results/tradeoff-study-20261027-v2/summary.csv), [paired differences](../results/tradeoff-study-20261027-v2/paired_differences.csv), and [manifest](../results/tradeoff-study-20261027-v2/manifest.json) are shareable. The full per-bin run logs are local and ignored by Git; rerun the command to regenerate them. The audit verifies run checksums, equal realized inputs for paired policies, causal observation timing, predicted carbon/peak guard records, and summary accounting. `tests/test_tradeoff.py` also checks causal decisions and the oracle on a small graph.

The subsequent [later-period follow-up](FOLLOWUP_STUDY.md) froze the planner/settings, trained twelve separate neural checkpoints, and evaluated 630 paired runs. Extra training did not consistently improve forecast error. That follow-up also discovered empty GÉANT source sections and severe saturation under the fixed capacities, limiting its interpretation. Never treat the two inspected validation days, earlier inspected test days, or the now-inspected follow-up outcomes as fresh evidence for another tuning round.
