"""Frozen later-period evaluation of longer training, expanded data, and link-load loss.

python -m carbonroute.followup all
Stages can be resumed independently: prepare, train, evaluate, report.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import abilene, followup_data
from .common import ROOT, fingerprint, load_json, save_json, sha256
from .data import CarbonTable
from .experiments import paired_differences, workload
from .prediction import (
    Persistence,
    Predictor,
    TrainedPredictor,
    batch_prediction,
    forecast_metrics,
    make_windows,
    train,
)
from .simulation import replay


def frozen_protocol(root: Path, output: Path) -> dict:
    source = root / "configs/followup_protocol.json"
    protocol = load_json(source)
    output.mkdir(parents=True, exist_ok=True)
    target = output / "protocol.json"
    if target.exists():
        if sha256(source) != sha256(target):
            raise ValueError("Frozen protocol changed; use a new explicitly documented study")
    else:
        shutil.copyfile(source, target)
        save_json(output / "protocol_record.json", {
            "frozen_utc": datetime.now(timezone.utc).isoformat(), "protocol_sha256": sha256(target),
            "rule": "No final test outcomes were used to select this protocol"})
    return protocol


def prepare(root: Path, protocol: dict) -> None:
    for name in ("geant", "abilene"):
        path = root / "inputs/processed/followup" / name / "manifest.json"
        if path.exists():
            data = followup_data.load(root, name)
            if data.manifest["protocol_hash"] != fingerprint(protocol):
                raise ValueError("Prepared follow-up data uses another protocol")
        else:
            data = followup_data.prepare(root, name, protocol)
        print(f"{name}: {data.manifest['split_dates']}", flush=True)


def variant_config(base: dict, settings: dict, seed: int | None = None) -> dict:
    cfg = dict(base)
    for field in ("epochs", "patience", "routing_loss_alpha"):
        cfg[field] = settings[field]
    if seed is not None:
        cfg["seed"] = seed
    return cfg


def training(root: Path, protocol: dict) -> None:
    for name in ("geant", "abilene"):
        original, base, _ = followup_data.reference(root, name)
        expanded = followup_data.load(root, name)
        for variant, settings in protocol["training_variants"].items():
            cfg = variant_config(base, settings, protocol["seed"])
            data = original if variant == "longer" else expanded
            folder = root / "artifacts/followup" / name / variant
            if (folder / "training_summary.json").exists():
                # Verify actual checkpoint checksums, not just completion flags.
                for kind in ("gnn", "gru"):
                    TrainedPredictor(folder, data, cfg, kind)
                meta = load_json(folder / "training_summary.json")
                if meta.get("test_evaluated") is not False:
                    raise ValueError("Training must not evaluate final test data")
                print(f"Reusing verified {name}/{variant}", flush=True)
                continue
            print(f"Training {name}/{variant} (no test evaluation)", flush=True)
            train(root, cfg, data, folder, evaluate_test=False)


def models(root: Path, name: str, protocol: dict) -> tuple[dict, dict]:
    original, cfg, folder = followup_data.reference(root, name)
    expanded = followup_data.load(root, name)
    found: dict[str, Predictor] = {}
    evidence: dict[str, Any] = {}
    for variant in ("reference", *protocol["training_variants"]):
        directory = folder if variant == "reference" else root / "artifacts/followup" / name / variant
        c = cfg if variant == "reference" else variant_config(cfg, protocol["training_variants"][variant], protocol["seed"])
        data = original if variant in ("reference", "longer") else expanded
        for kind in ("gnn", "gru"):
            label = f"{variant}_{kind}"
            found[label] = TrainedPredictor(directory, data, c, kind)
            meta = load_json(directory / f"{kind}.json")
            evidence[label] = {"checkpoint_sha256": sha256(directory / f"{kind}.pt"),
                               "metadata_sha256": sha256(directory / f"{kind}.json"),
                               "config": c, "training_traffic_sha256": data.manifest["traffic_sha256"],
                               "best_epoch": meta["best_epoch"],
                               "validation_mae_mbps": meta["validation_mae_mbps"],
                               "training_seconds": meta["training_seconds"]}
    for label, directory in (("reference_persistence", folder),
                              ("updated_persistence", root / "artifacts/followup" / name / "expanded")):
        info = load_json(directory / "persistence.json")
        expected_data = original if label == "reference_persistence" else expanded
        expected_cfg = cfg if label == "reference_persistence" else variant_config(
            cfg, protocol["training_variants"]["expanded"], protocol["seed"])
        if (info["traffic_sha256"] != expected_data.manifest["traffic_sha256"]
                or info["config_hash"] != fingerprint(expected_cfg)):
            raise ValueError("Persistence margin uses different traffic")
        found[label] = Persistence(cfg["horizon"], expanded.mask, np.array(info["margin_mbps"]))
        evidence[label] = {"metadata_sha256": sha256(directory / "persistence.json")}
    return found, evidence


def evaluate(root: Path, output: Path, protocol: dict) -> Path:
    # Freeze every scientific source, checkpoint and input hash before examining outcomes.
    scientific = ("followup.py", "followup_data.py", "prediction.py", "routing.py",
                  "simulation.py", "data.py", "network.py", "service.py", "experiments.py",
                  "abilene.py", "common.py")
    plan: dict[str, Any] = {"protocol_sha256": sha256(output / "protocol.json"),
            "environment": {"python": platform.python_version(),
                            **{name: importlib.metadata.version(name) for name in ("torch", "numpy", "pandas")}},
            "forecast_scope": "All contiguous windows inside the declared final test split; routing uses the first seven complete days",
            "source_sha256": {f: sha256(root / "src/carbonroute" / f) for f in scientific},
            "networks": {}}
    loaded: dict[str, Any] = {}
    for name in ("geant", "abilene"):
        original, cfg, _ = followup_data.reference(root, name)
        data = followup_data.load(root, name)
        predictors, evidence = models(root, name, protocol)
        windows = followup_data.test_days(data, cfg, protocol["test_days_per_network"])
        carbon_file = "carbon.csv" if name == "geant" else "eGRID2004_aggregation.xls"
        carbon_hash = original.manifest["sources"][carbon_file]["sha256"]
        if sha256(root / "inputs/raw" / carbon_file) != carbon_hash:
            raise ValueError("Carbon source changed before evaluation freeze")
        plan["networks"][name] = {"config": cfg, "traffic_sha256": data.manifest["traffic_sha256"],
                                   "carbon_file": f"inputs/raw/{carbon_file}", "carbon_sha256": carbon_hash,
                                   "sources": data.manifest["sources"], "graph_hash": data.network.graph_hash,
                                   "split_dates": data.manifest["split_dates"], "predictors": evidence,
                                   "days": [str(data.times[s])[:10] for s, _ in windows]}
        loaded[name] = (cfg, data, predictors, windows)
    plan_path = output / "evaluation_plan.json"
    if plan_path.exists():
        if load_json(plan_path) != plan:
            raise ValueError("Scientific code, model or input changed after final evaluation was frozen")
    else:
        save_json(plan_path, plan)
    manifest_path = output / "manifest.json"
    manifest: dict[str, Any] = load_json(manifest_path) if manifest_path.exists() else {
        "schema_version": 1, "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_plan_sha256": sha256(plan_path), "source_sha256": plan["source_sha256"],
        "networks": plan["networks"], "runs": [],
        "interpretation": "First outcome evaluation on these later periods in recorded project experiments; one seed, adjacent days, simulated workloads and carbon proxy"}
    if manifest["evaluation_plan_sha256"] != sha256(plan_path):
        raise ValueError("Evaluation plan checksum mismatch")
    if manifest["status"] == "complete":
        for filename in ("summary.csv", "forecast_metrics.csv", "paired_differences.csv", "day_cluster_intervals.csv"):
            if sha256(output / filename) != manifest[filename.removesuffix(".csv") + "_sha256"]:
                raise ValueError("Completed follow-up evidence changed")
        print("Reusing completed, checksum-verified final evaluation", flush=True)
        return output
    (output / "runs").mkdir(exist_ok=True)
    save_json(manifest_path, manifest)
    existing = {r["run_id"]: r for r in manifest["runs"]}
    rows: list[dict[str, Any]] = []
    forecast_rows: list[dict[str, Any]] = []
    for name, (cfg, data, predictors, windows) in loaded.items():
        lo, hi = data.manifest["splits"]["test"]
        if name == "geant":
            original, _, _ = followup_data.reference(root, name)
            carbon = CarbonTable(root / "inputs/raw/carbon.csv")
            if carbon.source_hash != original.manifest["sources"]["carbon.csv"]["sha256"]:
                raise ValueError("Changed country-carbon source")
            ci_all, alignment = carbon.pair(data.times[lo:hi], protocol["carbon_year_geant"])
            save_json(output / "geant_alignment.json", alignment)
            year = protocol["carbon_year_geant"]
        else:
            original, _, _ = followup_data.reference(root, name)
            rates = np.array([original.manifest["epa_annual_g_per_kwh"][r] for r in abilene.REGION])
            ci_all = np.repeat(rates[None], hi-lo, axis=0)
            year = 2004
        # Final forecast scores are measured only after the evaluation plan is frozen.
        x, y, _ = make_windows(data, cfg, "test")
        train_lo, train_hi = data.manifest["splits"]["train"]
        threshold = float(np.quantile(data.rates[train_lo:train_hi, data.mask.astype(bool)], .9))
        for label, predictor in predictors.items():
            prediction = (batch_prediction(predictor.model, x, predictor.scale, cfg["batch_size"])
                          if isinstance(predictor, TrainedPredictor)
                          else np.repeat(x[:, -1:], cfg["horizon"], axis=1))
            forecast_rows.extend({"network": name, "model": label, **r} for r in
                                 forecast_metrics(y, prediction, predictor.margin, data.mask, threshold))
        del x, y
        for day, (start, stop) in enumerate(windows):
            for scenario in protocol["scenarios"]:
                seed = protocol["seed"] + day * 101
                traffic = workload(data, cfg, start, stop, scenario, seed)
                traffic_hash = hashlib.sha256(traffic[start-cfg["lookback"]:stop].tobytes()).hexdigest()
                ci = ci_all[start-lo:stop-lo]
                cases = [("shortest_path", "shortest_path", "reference_persistence"),
                         ("reactive_carbon", "reactive_carbon", "reference_persistence"),
                         ("predictive_carbon", "predictive_carbon", "reference_gnn"),
                         ("tradeoff_reactive", "tradeoff_reactive", "reference_persistence"),
                         ("oracle_current_bin", "oracle_current_bin", "reference_persistence")]
                for label in predictors:
                    kind = "persistence" if label.endswith("persistence") else label.rsplit("_", 1)[1]
                    cases.append((f"tradeoff_{label}", f"tradeoff_{kind}", label))
                for label, policy, predictor_name in cases:
                    run_id = f"{name}_d{day}_{scenario}_{label}"
                    path = output / "runs" / f"{run_id}.json"
                    if run_id in existing:
                        if sha256(path) != existing[run_id]["sha256"]:
                            raise ValueError("Saved run changed during resume")
                        rows.append(load_json(path)["summary"])
                        continue
                    if path.exists():
                        raise ValueError("Unmanifested run exists; inspect before resuming")
                    result = replay(data, cfg, traffic, ci, start, stop, policy,
                                    predictors[predictor_name], protocol["planner"]["observation_delay_bins"],
                                    protocol["planner"]["carbon_budget_fraction"],
                                    protocol["planner"]["congestion_weight"],
                                    protocol["planner"]["change_penalty"])
                    row = {"network": name, "window": day, "scenario": scenario, "carbon_year": year,
                           "traffic_day": str(data.times[start])[:10], "seed": seed,
                           "traffic_sha256": traffic_hash, "predictor": predictor_name,
                           **result.summary, "policy": label}
                    save_json(path, {"summary": row, "records": result.records})
                    rows.append(row)
                    entry = {"run_id": run_id, "file": f"runs/{run_id}.json", "sha256": sha256(path)}
                    manifest["runs"].append(entry)
                    save_json(manifest_path, manifest)
                print(f"Completed later test {name} day {day+1}/{len(windows)}, {scenario}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "summary.csv", index=False)
    pd.DataFrame(forecast_rows).to_csv(output / "forecast_metrics.csv", index=False)
    intervals = []
    for name, group in frame.groupby("network"):
        intervals.append(paired_differences(group, protocol["seed"]).assign(network=name))
    pd.concat(intervals, ignore_index=True).to_csv(output / "day_cluster_intervals.csv", index=False)
    baseline = frame[frame.policy == "reactive_carbon"]
    joined = frame.merge(baseline, on=["network", "window", "scenario"], suffixes=("", "_reactive"),
                         validate="many_to_one")
    metrics = ("forwarding_score", "served_fraction", "overload_minutes", "route_changes")
    for metric in metrics:
        joined[f"delta_{metric}"] = joined[metric] - joined[f"{metric}_reactive"]
    cols = ["network", "window", "scenario", "policy"] + [f"delta_{m}" for m in metrics]
    joined[cols].to_csv(output / "paired_differences.csv", index=False)
    for filename in ("summary.csv", "forecast_metrics.csv", "paired_differences.csv", "day_cluster_intervals.csv"):
        manifest[filename.removesuffix(".csv") + "_sha256"] = sha256(output / filename)
    manifest["status"] = "complete"
    save_json(manifest_path, manifest)
    print(f"Saved {len(frame)} later-period paired runs", flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "train", "evaluate", "report", "all"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "results/followup-study-20261027").resolve()
    protocol = frozen_protocol(root, output)
    if args.command in ("prepare", "all"):
        prepare(root, protocol)
    if args.command in ("train", "all"):
        training(root, protocol)
    if args.command in ("evaluate", "all"):
        evaluate(root, output, protocol)
    if args.command in ("report", "all"):
        from .followup_report import report
        report(output)


if __name__ == "__main__":
    main()
