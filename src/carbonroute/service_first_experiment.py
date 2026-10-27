"""Frozen comparison of service-first routing on later trace periods."""
from __future__ import annotations

import argparse
import hashlib
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import abilene
from .common import ROOT, load_json, save_json, sha256
from .data import CarbonTable, Prepared, parse_demand, read_archive
from .experiments import paired_differences, workload
from .followup_data import reference
from .network import section
from .service_first_simulation import replay
from .tradeoff_experiment import predictors


def input_data(root: Path, name: str, protocol: dict) -> tuple[Prepared, dict, dict]:
    original, cfg, _ = reference(root, name)
    source: dict[str, Any] = {}
    if name == "geant":
        path = root / "inputs/raw/geant-traffic.tgz"
        if sha256(path) != original.manifest["sources"][path.name]["sha256"]:
            raise ValueError("Changed GÉANT source")
        times, full, _ = read_archive(path)
        lo, hi = map(np.datetime64, protocol["geant_source_range"])
        keep = (times >= lo) & (times < hi)
        times, full = times[keep], full[keep]
        start = np.datetime64(protocol["geant_start"])
        end = start + np.timedelta64(protocol["test_days"], "D")
        history_start = start - np.timedelta64(cfg["lookback"] * cfg["bin_seconds"], "s")
        empty = []
        with tarfile.open(path, "r|gz") as archive:
            for member in archive:
                if not member.isfile() or not member.name.endswith(".txt"):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Missing archive member")
                text = stream.read().decode("utf-8")
                stamp, _, _ = parse_demand(text)
                if history_start <= stamp < end and not section(text, "DEMANDS"):
                    empty.append(str(stamp))
        source = {"traffic_sha256": sha256(path), "empty_native_sections": empty,
                  "availability_rule": protocol["geant_source_rule"]}
        if empty:
            raise ValueError(f"Predeclared GÉANT dates fail source-availability rule: {len(empty)} empty bins")
    else:
        path = root / "inputs/raw/AbileneTM-all.tar"
        expected = load_json(root / "configs/followup_protocol.json")["abilene"]["archive_sha256"]
        if sha256(path) != expected:
            raise ValueError("Changed Abilene source archive")
        weeks = []
        members = {}
        with tarfile.open(path) as archive:
            for number, first in protocol["abilene_weeks"]:
                filename = f"X{number:02}.gz"
                member = archive.getmember(filename)
                stream = archive.extractfile(member)
                if stream is None or member.size > 20_000_000:
                    raise ValueError("Invalid Abilene source member")
                content = stream.read()
                target = root / "inputs/raw/abilene" / filename
                digest = hashlib.sha256(content).hexdigest()
                if target.exists() and sha256(target) != digest:
                    raise ValueError("Cached Abilene week differs from verified archive")
                if not target.exists():
                    target.write_bytes(content)
                members[filename] = digest
                weeks.append(abilene.read_week(target, first))
        times = np.concatenate([week[0] for week in weeks])
        full = np.concatenate([week[1] for week in weeks])
        source = {"traffic_sha256": sha256(path), "members": members}
    rates = full * original.mask * original.manifest["traffic_factor"]
    data = Prepared(times, rates, original.mask, original.scale, original.network, original.pairs,
                    original.manifest)
    return data, cfg, source


def run(root: Path, output: Path) -> None:
    protocol_path = root / "configs/service_first_protocol.json"
    protocol = load_json(protocol_path)
    output.mkdir(parents=True, exist_ok=True)
    frozen = output / "protocol.json"
    if frozen.exists() and sha256(frozen) != sha256(protocol_path):
        raise ValueError("Protocol changed; choose a new study")
    if not frozen.exists():
        frozen.write_bytes(protocol_path.read_bytes())
        save_json(output / "protocol_record.json", {"frozen_utc": datetime.now(timezone.utc).isoformat(),
                  "protocol_sha256": sha256(frozen), "note": "Written before final outcomes"})
    inputs = {}
    plan: dict[str, Any] = {"protocol_sha256": sha256(frozen), "networks": {},
        "source_sha256": {name: sha256(Path(__file__).with_name(name)) for name in
                          ("service_first_experiment.py", "service_first.py", "service_first_simulation.py",
                           "routing.py", "simulation.py", "service.py", "data.py", "prediction.py",
                           "network.py", "common.py", "experiments.py", "abilene.py", "tradeoff_experiment.py")}}
    for name in ("geant", "abilene"):
        data, cfg, source = input_data(root, name, protocol)
        original, _, folder = reference(root, name)
        models = predictors(root, original, cfg, folder)
        day_start = np.datetime64(protocol[f"{name}_start"])
        bins = 86400 // cfg["bin_seconds"]
        windows = []
        for day in range(protocol["test_days"]):
            stamp = day_start + np.timedelta64(day, "D")
            index = int(np.searchsorted(data.times, stamp))
            if (index < cfg["lookback"] or index + bins > len(data.times) or data.times[index] != stamp or
                    not np.all(np.diff(data.times[index-cfg["lookback"]:index+bins]) ==
                               np.timedelta64(cfg["bin_seconds"], "s"))):
                raise ValueError(f"Missing predeclared contiguous source day: {name} {stamp}")
            windows.append((index, index + bins))
        carbon_path = root / ("inputs/raw/carbon.csv" if name == "geant" else "inputs/raw/eGRID2004_aggregation.xls")
        if sha256(carbon_path) != original.manifest["sources"][carbon_path.name]["sha256"]:
            raise ValueError("Changed carbon source")
        if name == "geant":
            carbon, alignment = CarbonTable(carbon_path).pair(data.times, 2022)
            save_json(output / "geant_alignment.json", alignment)
        else:
            ci = np.array([original.manifest["epa_annual_g_per_kwh"][code] for code in abilene.REGION])
            carbon = np.repeat(ci[None], len(data.times), axis=0)
        plan["networks"][name] = {"config": cfg, "days": [str(data.times[a])[:10] for a, _ in windows],
            "source": source, "graph_hash": data.network.graph_hash, "carbon_sha256": sha256(carbon_path),
            "prepared_rates_sha256": hashlib.sha256(data.rates.tobytes()).hexdigest(),
            "predictor_sha256": {f: sha256(folder / f) for f in ("gnn.pt", "gnn.json", "persistence.json")}}
        inputs[name] = (data, cfg, models, windows, carbon)
    plan_path = output / "evaluation_plan.json"
    if plan_path.exists() and load_json(plan_path) != plan:
        raise ValueError("Sources or models changed after evaluation freeze")
    if not plan_path.exists():
        save_json(plan_path, plan)
    manifest_path = output / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {
        "status": "running", "evaluation_plan_sha256": sha256(plan_path), "networks": plan["networks"],
        "runs": [], "protocol_sha256": sha256(frozen)}
    if manifest["evaluation_plan_sha256"] != sha256(plan_path):
        raise ValueError("Changed evaluation plan")
    if manifest["status"] == "complete":
        for filename in ("summary.csv", "paired_differences.csv", "day_cluster_intervals.csv"):
            if sha256(output / filename) != manifest[filename.removesuffix(".csv") + "_sha256"]:
                raise ValueError("Changed completed results")
        print("Reusing complete, checksum-verified study", flush=True)
        return
    (output / "runs").mkdir(exist_ok=True)
    existing = {item["run_id"]: item for item in manifest["runs"]}
    rows = []
    for name, (data, cfg, models, windows, carbon) in inputs.items():
        for day, (start, stop) in enumerate(windows):
            for scenario in protocol["workloads"]:
                seed = protocol["seed"] + 101 * day
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
                        raise ValueError("Unmanifested run exists")
                    model = "gnn" if policy.endswith("gnn") or policy == "predictive_te" else "persistence"
                    result = replay(data, cfg, rates, carbon[start:stop], start, stop, policy, models[model], 1)
                    offered = np.sum([r["offered_mbps"] for r in result.records], axis=0)
                    served = np.sum([r["served_mbps"] for r in result.records], axis=0)
                    fractions = np.divide(served, offered, out=np.ones_like(served), where=offered > 0)
                    weighted_delay = sum(sum(r["served_mbps"][i] * data.network.delay(tuple(route))
                                             for i, route in enumerate(r["routes"])) for r in result.records)
                    row = {"network": name, "window": day, "scenario": scenario,
                           "traffic_day": str(data.times[start])[:10], "carbon_year": 2022 if name == "geant" else 2004,
                           "seed": seed, "traffic_sha256": traffic_hash, **result.summary,
                           "min_pair_service_fraction": float(fractions[offered > 0].min()) if (offered > 0).any() else None,
                           "mean_served_path_delay_ms": float(weighted_delay / served.sum()) if served.sum() else None}
                    save_json(path, {"summary": row, "records": result.records})
                    rows.append(row)
                    manifest["runs"].append({"run_id": run_id, "file": f"runs/{run_id}.json", "sha256": sha256(path)})
                    save_json(manifest_path, manifest)
                print(f"Completed {name} day {day+1}/{len(windows)}, {scenario}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "summary.csv", index=False)
    baseline = frame[frame.policy == "reactive_carbon"]
    joined = frame.merge(baseline, on=["network", "window", "scenario"], suffixes=("", "_reactive"), validate="many_to_one")
    metrics = ("forwarding_score", "served_fraction", "overload_minutes", "route_changes", "min_pair_service_fraction")
    for metric in metrics:
        joined[f"delta_{metric}"] = joined[metric] - joined[f"{metric}_reactive"]
    joined[["network", "window", "traffic_day", "scenario", "policy"] +
           [f"delta_{metric}" for metric in metrics]].to_csv(output / "paired_differences.csv", index=False)
    pd.concat([paired_differences(group, protocol["seed"]).assign(network=name)
               for name, group in frame.groupby("network")], ignore_index=True).to_csv(output / "day_cluster_intervals.csv", index=False)
    for filename in ("summary.csv", "paired_differences.csv", "day_cluster_intervals.csv"):
        manifest[filename.removesuffix(".csv") + "_sha256"] = sha256(output / filename)
    manifest["status"] = "complete"
    save_json(manifest_path, manifest)
    print(f"Saved {len(frame)} paired runs", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "results/service-first-20261027")
    args = parser.parse_args()
    run(args.root.resolve(), args.output.resolve())
