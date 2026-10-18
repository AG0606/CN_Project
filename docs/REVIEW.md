# Two-axis implementation review

Reviewed the implementation diff `c05e3d9...9af9d2b` against `CODING_STANDARDS.md`, `docs/ARCHITECTURE.md` and the accepted `IMPLEMENTATION_PLAN.md` on 18 October 2026.

## Standards

**Finding (resolved):** The first campaign format hashed only aggregate/forecast files. A replay or carbon alignment JSON file could have changed while the report still generated, violating the architecture contract for checked frozen evidence. The final campaign format (schema 2) stores SHA-256 hashes for every run and country/date mapping. The reporter verifies each hash, validates run identities against the aggregate table, and refuses inconsistencies. A deliberate modification of either a run or alignment file was rejected in local verification. No material code-smell finding was reported.

## Spec

The independent spec review found no substantive defect in the agreed native Windows scope. The graph, dynamic traffic, country carbon, GNN, chronological training, guarded comparisons, service allocator, causality, component ablations and paired experiment design were all present. The optional Mininet/OpenFlow extension remains explicitly unimplemented and is not claimed as evidence.

**Handoff check:** A ZIP extracted in a second local folder reproduced preparation and reran the pilot with the bundled checkpoint. The friend’s actual Windows laptop has not been tested. The team should open `DEMO.html`, then run `SETUP.ps1` and `RUN_DEMO.ps1 -Rebuild` on that laptop before presenting there.

## Outcome

Standards: one substantive finding, fixed. Spec: zero implementation findings. The remaining external validation is the friend's laptop, where environment details are unknown.
