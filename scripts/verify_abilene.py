"""Verify the finished Abilene campaign against its source and per-bin records."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from carbonroute.abilene import REGION, egrid_rates
from carbonroute.common import ROOT, sha256


def verify(root: Path = ROOT, output: Path | None = None) -> None:
    output = output or root / "results/abilene"
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["dataset"] == "abilene-egrid2004"
    assert manifest["config"]["bin_seconds"] == 300
    assert len(manifest["graph"]["node_ids"]) == 12
    assert len(manifest["graph"]["arcs"]) == 30
    assert len(manifest["runs"]) == 42
    assert sha256(output / "summary.csv") == manifest["summary_sha256"]
    for filename, info in manifest["traffic_manifest"]["sources"].items():
        path = (root / "inputs/raw/abilene" / filename if filename.startswith("X") else
                root / "inputs/raw" / filename)
        assert sha256(path) == info["sha256"], filename
    _, grams = egrid_rates(root / "inputs/raw/eGRID2004_aggregation.xls")
    expected_ci = np.array([grams[code] for code in REGION])
    by_case: dict[tuple[int, str], list[dict]] = defaultdict(list)
    summary = pd.read_csv(output / "summary.csv")
    for entry in manifest["runs"]:
        path = output / entry["file"]
        assert sha256(path) == entry["sha256"]
        run = json.loads(path.read_text())
        records = run["records"]
        row = run["summary"]
        assert len(records) == row["bins"] == 288
        assert row["policy"] == entry["policy"]
        assert np.allclose([r["carbon"] for r in records], expected_ci[None, :])
        assert all(np.isfinite(r["link_utilization"]).all() for r in records)
        assert math.isclose(row["forwarding_score"],
                            sum(r["carbon_weighted_mb"] for r in records) /
                            sum(r["served_mb"] for r in records), rel_tol=1e-10)
        assert math.isclose(row["overload_minutes"],
                            sum(max(r["link_utilization"]) > 1 + 1e-9 for r in records) * 5)
        assert (summary.run_id == row["run_id"]).sum() == 1
        by_case[(entry["window"], entry["scenario"])].append(run)
    assert len(by_case) == 6
    for runs in by_case.values():
        assert len(runs) == 7
        reference = np.array([r["offered_mbps"] for r in runs[0]["records"]])
        assert all(np.array_equal(reference, np.array([r["offered_mbps"] for r in run["records"]]))
                   for run in runs[1:])
    print("Verified 42 paired runs, source checksums, annual EPA values, summaries, and equal demands")


if __name__ == "__main__":
    verify()
