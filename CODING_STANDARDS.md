# Project standards

- Keep forecasting, path planning, service allocation and reporting separate. Use the public contracts in docs/ARCHITECTURE.md.
- Represent rates in decimal Mbps, bin durations in seconds, and carbon in g CO2/kWh (numerically kg CO2/MWh). State any modeled conversion explicitly.
- Never expose future demand or future carbon to a predictor/planner. Fit transforms and pair selection on training only; calibrate margins on validation only.
- All policies must use the same workload, graph, allocator, candidate set and declared observation timing. Preserve unfavorable results.
- Do not silently replace missing/corrupt data, mismatched checkpoints, absent countries or failed runs with synthetic success.
- New dependencies must be free, documented and pinned for reproduction. Raw source downloads and generated artifacts stay outside Git.
- Typecheck Python with mypy and lint with Ruff. Test externally observable behavior and independently calculated invariants; avoid tests that merely restate implementation.
- Results are simulation outputs. Do not label them packet measurements, proven physical carbon savings or OpenFlow validation.
