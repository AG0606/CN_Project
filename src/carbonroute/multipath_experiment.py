"""Predeclared paired multipath campaign on later GÉANT and Abilene periods."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import abilene
from .common import ROOT, load_json, save_json, sha256
from .data import CarbonTable
from .experiments import workload
from .followup_data import reference
from .multipath_simulation import replay
from .service_first_experiment import input_data
from .tradeoff_experiment import predictors


def intervals(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    rows = []
    for (network, scenario), group in frame.groupby(["network", "scenario"]):
        baseline = group[group.policy == "reactive_carbon"]
        for policy, selected in group.groupby("policy", sort=False):
            if policy == "reactive_carbon":
                continue
            paired = selected.merge(baseline, on="window", suffixes=("", "_reactive"), validate="one_to_one")
            for metric in ("forwarding_score", "served_fraction", "overload_minutes", "route_changes", "min_pair_service_fraction"):
                values = (paired[metric] - paired[metric+"_reactive"]).dropna().to_numpy()
                if not len(values):
                    continue
                rng = np.random.default_rng(seed)
                boot = rng.choice(values, (2000, len(values)), replace=True).mean(axis=1)
                low, high = np.quantile(boot, [.025, .975])
                rows.append({"network": network, "scenario": scenario, "policy": policy, "metric": metric,
                             "difference_vs_reactive": float(values.mean()), "ci95_low": float(low),
                             "ci95_high": float(high), "defined_day_clusters": len(values)})
    return pd.DataFrame(rows)


def run(root: Path, output: Path) -> None:
    protocol_path = root / "configs/multipath_protocol.json"
    protocol = load_json(protocol_path)
    output.mkdir(parents=True, exist_ok=True)
    frozen = output / "protocol.json"
    if frozen.exists() and sha256(frozen) != sha256(protocol_path):
        raise ValueError("Changed protocol; use a new documented study")
    if not frozen.exists():
        frozen.write_bytes(protocol_path.read_bytes())
        save_json(output / "protocol_record.json", {"frozen_utc": datetime.now(timezone.utc).isoformat(),
                  "protocol_sha256": sha256(frozen), "note": "Recorded before final routing outcomes"})
    science = ("multipath_experiment.py", "multipath.py", "multipath_simulation.py", "service_first_experiment.py",
               "service_first.py", "service_first_simulation.py", "routing.py", "simulation.py", "service.py",
               "data.py", "prediction.py", "network.py", "common.py", "experiments.py", "abilene.py",
               "followup_data.py", "tradeoff_experiment.py")
    plan: dict[str, Any] = {"protocol_sha256": sha256(frozen), "networks": {},
        "source_sha256": {name: sha256(Path(__file__).with_name(name)) for name in science},
        "environment": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                         for name in ("numpy", "scipy", "torch", "pandas")}}}
    loaded = {}
    for name in ("geant", "abilene"):
        data, cfg, source = input_data(root, name, protocol)
        original, _, folder = reference(root, name)
        models = predictors(root, original, cfg, folder)
        start_day = np.datetime64(protocol[f"{name}_start"])
        bins = 86400 // cfg["bin_seconds"]
        windows = []
        for day in range(protocol["test_days"]):
            stamp = start_day + np.timedelta64(day, "D")
            start = int(np.searchsorted(data.times, stamp))
            if (start < cfg["lookback"] or start+bins > len(data.times) or data.times[start] != stamp or
                    not np.all(np.diff(data.times[start-cfg["lookback"]:start+bins]) ==
                               np.timedelta64(cfg["bin_seconds"], "s"))):
                raise ValueError(f"Unavailable predeclared day {name} {stamp}")
            windows.append((start, start+bins))
        carbon_path = root / ("inputs/raw/carbon.csv" if name == "geant" else "inputs/raw/eGRID2004_aggregation.xls")
        if sha256(carbon_path) != original.manifest["sources"][carbon_path.name]["sha256"]:
            raise ValueError("Changed carbon source")
        if name == "geant":
            carbon, alignment = CarbonTable(carbon_path).pair(data.times, 2022)
            save_json(output / "geant_alignment.json", alignment)
        else:
            annual = np.array([original.manifest["epa_annual_g_per_kwh"][code] for code in abilene.REGION])
            carbon = np.repeat(annual[None], len(data.times), axis=0)
        plan["networks"][name] = {"config": cfg, "source": source, "graph_hash": data.network.graph_hash,
            "days": [str(data.times[a])[:10] for a, _ in windows], "carbon_sha256": sha256(carbon_path),
            "prepared_rates_sha256": hashlib.sha256(data.rates.tobytes()).hexdigest(),
            "reference_traffic_sha256": original.manifest["traffic_sha256"],
            "predictor_sha256": {f: sha256(folder / f) for f in ("gnn.pt", "gnn.json", "persistence.json")}}
        loaded[name] = (data, cfg, models, windows, carbon)
    plan_path = output / "evaluation_plan.json"
    if plan_path.exists() and load_json(plan_path) != plan:
        raise ValueError("Scientific source, model, input or environment changed after freeze")
    if not plan_path.exists():
        save_json(plan_path, plan)
    manifest_path = output / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {
        "status": "running", "evaluation_plan_sha256": sha256(plan_path), "networks": plan["networks"],
        "protocol_sha256": sha256(frozen), "runs": []}
    if manifest["evaluation_plan_sha256"] != sha256(plan_path):
        raise ValueError("Changed evaluation plan")
    if manifest["status"] == "complete":
        for filename in ("summary.csv", "paired_differences.csv", "day_cluster_intervals.csv"):
            if sha256(output / filename) != manifest[filename.removesuffix(".csv")+"_sha256"]:
                raise ValueError("Changed completed evidence")
        print("Reusing complete, checksum-verified multipath study", flush=True)
        return
    (output / "runs").mkdir(exist_ok=True)
    existing = {item["run_id"]: item for item in manifest["runs"]}
    rows = []
    for name, (data, cfg, models, windows, carbon) in loaded.items():
        for day, (start, stop) in enumerate(windows):
            for scenario in protocol["workloads"]:
                seed = protocol["seed"] + day*101
                rates = workload(data, cfg, start, stop, scenario, seed)
                traffic_hash = hashlib.sha256(rates[start-cfg["lookback"]:stop].tobytes()).hexdigest()
                for policy in protocol["policies"]:
                    run_id = f"{name}_d{day}_{scenario}_{policy}"
                    path = output / "runs" / f"{run_id}.json"
                    if run_id in existing:
                        if sha256(path) != existing[run_id]["sha256"]:
                            raise ValueError("Changed saved run")
                        rows.append(load_json(path)["summary"])
                        continue
                    if path.exists():
                        raise ValueError("Unmanifested run; inspect before continuing")
                    model = "gnn" if "gnn" in policy else "persistence"
                    result = replay(data, cfg, rates, carbon[start:stop], start, stop, policy, models[model])
                    row = {"network": name, "window": day, "traffic_day": str(data.times[start])[:10],
                           "scenario": scenario, "seed": seed, "traffic_sha256": traffic_hash,
                           "carbon_year": 2022 if name == "geant" else 2004, **result["summary"]}
                    result["summary"] = row
                    save_json(path, result)
                    rows.append(row)
                    manifest["runs"].append({"run_id": run_id, "file": f"runs/{run_id}.json", "sha256": sha256(path)})
                    save_json(manifest_path, manifest)
                print(f"Completed multipath {name} day {day+1}/{len(windows)}, {scenario}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "summary.csv", index=False)
    baseline = frame[frame.policy == "reactive_carbon"]
    paired = frame.merge(baseline, on=["network", "window", "scenario"], suffixes=("", "_reactive"), validate="many_to_one")
    metrics = ("forwarding_score", "served_fraction", "overload_minutes", "route_changes", "min_pair_service_fraction")
    for metric in metrics:
        paired["delta_"+metric] = paired[metric]-paired[metric+"_reactive"]
    paired[["network", "window", "traffic_day", "scenario", "policy"]+
           ["delta_"+metric for metric in metrics]].to_csv(output / "paired_differences.csv", index=False)
    intervals(frame, protocol["seed"]).to_csv(output / "day_cluster_intervals.csv", index=False)
    for filename in ("summary.csv", "paired_differences.csv", "day_cluster_intervals.csv"):
        manifest[filename.removesuffix(".csv")+"_sha256"] = sha256(output / filename)
    manifest["status"] = "complete"
    save_json(manifest_path, manifest)
    print(f"Saved {len(frame)} paired multipath runs", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "results/multipath-20261027-v2")
    args = parser.parse_args()
    run(args.root.resolve(), args.output.resolve())
