# Dashboard matching the final paper

Open `results/final-validation-20261027/dashboard.html` in current Chrome or Edge.
The file is self-contained and works offline. It retains the earlier FFCS-inator
layout and fonts. The old `results/demo/index.html` is unchanged.

- Default: congested traffic, 10 Mbps, three-seed Table 3 aggregation.
- Table 4 view: seed 42, with 10/20/40 Mbps controls and a capacity comparison.
- Headline cards and the main comparison cover all seven test days. Served demand
  pools bytes; other metrics average the relevant runs.
- Replay uses the first chronological final-test day and seed 42 for neural
  policies. It displays every active path fraction, not a single representative
  path. Predicted peak is explicitly unavailable because final logs did not save it.
- Forecast results use the final evaluation (Table 2); the perfect-demand table
  reproduces the zero-margin comparisons at 10 Mbps (Table 5).
- Historical campaign outcomes are not embedded. Only hash-matched static graph
  metadata is reused from old manifests. All 2,058 final summary rows are embedded,
  along with 180 checksum-verified first-day causal replays compressed inside HTML.

Regenerate from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/build_paper_dashboard.py
```

The builder verifies final CSV hashes against the completed manifest and audit,
checks each embedded replay hash, and asserts numerical anchors from the paper.
It does not retrain models, rerun experiments, or modify frozen outcomes.
