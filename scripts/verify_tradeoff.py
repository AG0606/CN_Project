"""Audit saved tradeoff pilot logs, input pairing, accounting, and decision timing."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from carbonroute.common import load_json, sha256


def verify(folder: Path) -> None:
    manifest = load_json(folder / "manifest.json")
    if manifest["status"] != "complete":
        raise ValueError("Incomplete campaign")
    for filename, key in (("summary.csv", "summary_sha256"),
                          ("paired_differences.csv", "paired_differences_sha256")):
        if sha256(folder / filename) != manifest[key]:
            raise ValueError(f"Changed evidence: {filename}")
    summary = pd.read_csv(folder / "summary.csv")
    indexed = summary.set_index(["network", "window", "scenario", "policy"])
    if not indexed.index.is_unique:
        raise ValueError("Duplicate paired policy summaries")
    seen = {}
    for item in manifest["runs"]:
        path = (folder / item["file"]).resolve()
        if not path.is_relative_to((folder / "runs").resolve()) or sha256(path) != item["sha256"]:
            raise ValueError(f"Invalid run path or checksum: {item['run_id']}")
        run = load_json(path)
        row, records = run["summary"], run["records"]
        key = (row["network"], row["window"], row["scenario"])
        input_bytes = json.dumps([(r["traffic_time"], r["offered_mbps"], r["carbon"]) for r in records],
                                 separators=(",", ":")).encode()
        inputs = hashlib.sha256(input_bytes).hexdigest()
        if key in seen and seen[key] != inputs:
            raise ValueError(f"Policies used different realized inputs: {key}")
        seen[key] = inputs
        oracle = row["policy"] == "oracle_current_bin"
        for r in records:
            if oracle and r["observed_through"] != r["traffic_time"]:
                raise ValueError("Oracle must be marked as using current demand")
            if not oracle and r["observed_through"] >= r["traffic_time"]:
                raise ValueError("Causal policy observed current or future demand")
            if row["policy"].startswith(("tradeoff_", "joint_")):
                if (not r["carbon_budget_met"] or r["predicted_carbon_cost"] >
                        r["reactive_carbon_budget"] + 1e-7):
                    raise ValueError("Predicted carbon budget violation")
            if row["policy"].startswith("tradeoff_") and (
                    r["projected_max_utilization"] > r["projected_peak_limit"] + 1e-7):
                raise ValueError("Predicted peak guard violation")
            if row["policy"].startswith("tradeoff_"):
                expected = max(manifest["networks"][row["network"]]["config"]["utilization_limit"],
                               r["projected_reference_peak"])
                if not np.isclose(r["projected_peak_limit"], expected):
                    raise ValueError("Incorrect predicted peak guard")
        served = sum(r["served_mb"] for r in records)
        weighted = sum(r["carbon_weighted_mb"] for r in records)
        overload = sum(max(r["link_utilization"]) > 1 + 1e-9 for r in records)
        overload *= manifest["networks"][row["network"]]["config"]["bin_seconds"] / 60
        if served == 0 and weighted != 0:
            raise ValueError("Carbon attribution with no served bytes")
        score = weighted / served if served > 0 else float("nan")
        for field, value in (("served_mb", served), ("forwarding_score", score),
                             ("overload_minutes", overload)):
            saved = float(indexed.loc[(*key, row["policy"]), field])
            if not np.isclose(saved, value, rtol=1e-8, atol=1e-8, equal_nan=True):
                raise ValueError(f"Summary mismatch for {item['run_id']}: {field}")
    if len(manifest["runs"]) != len(summary):
        raise ValueError("Missing or extra summary rows")
    print(f"Verified {len(summary)} runs across {len(seen)} paired input cases; "
          "checksums, timing, predicted budgets and summary accounting match.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    verify(parser.parse_args().folder.resolve())
