"""Exploratory paired validation of budgeted tradeoff planners and a clairvoyant oracle.

Run: python -m carbonroute.tradeoff_experiment --output results/tradeoff-study
This deliberately uses already-inspected validation periods, never a fresh test.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import abilene
from .common import ROOT, config, fingerprint, load_json, save_json, sha256
from .data import CarbonTable, Prepared, load_prepared
from .experiments import workload
from .prediction import Persistence, TrainedPredictor
from .simulation import replay


def validation_days(data: Prepared, cfg: dict, count: int) -> list[tuple[int, int]]:
    lo, hi = data.manifest["splits"]["validation"]
    bins = 86400 // cfg["bin_seconds"]
    starts = [k for k in range(lo + cfg["lookback"], hi - bins + 1)
              if data.times[k] == data.times[k].astype("datetime64[D]")
              and np.all(np.diff(data.times[k-cfg["lookback"]:k+bins])
                         == np.timedelta64(cfg["bin_seconds"], "s"))]
    if len(starts) < count:
        raise ValueError(f"Only {len(starts)} contiguous validation days are available")
    return [(k, k + bins) for k in starts[:count]]


def predictors(root: Path, data: Prepared, cfg: dict, folder: Path) -> dict:
    meta = load_json(folder / "persistence.json")
    if (meta["config_hash"] != fingerprint(cfg)
            or meta["traffic_sha256"] != data.manifest["traffic_sha256"]):
        raise ValueError("Persistence evidence does not match the prepared data")
    return {"gnn": TrainedPredictor(folder, data, cfg, "gnn"),
            "gru": TrainedPredictor(folder, data, cfg, "gru"),
            "persistence": Persistence(cfg["horizon"], data.mask, np.array(meta["margin_mbps"]))}


def run(root: Path, output: Path, count: int = 2) -> Path:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Choose a new empty result directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "runs").mkdir()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    study: dict[str, Any] = {"schema_version": 1, "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
             "interpretation": "Exploratory validation periods already used for model selection; no fresh test claims.",
             "source_revision": revision,
             "source_sha256": {p.name: sha256(p) for p in (Path(__file__), Path(__file__).with_name("routing.py"),
                                                               Path(__file__).with_name("simulation.py"))},
             "parameters": {"carbon_budget_fractions": [0, 0.02], "congestion_weight": 1.0,
                            "per_flow_switch_penalty": 0.005, "observation_delay_bins": 1,
                            "peak_guard": "max(80% planning guard, reference peak under same forecast)",
                            "scenarios": ["normal", "congested", "bursty"], "days_per_network": count},
             "oracle": "Clairvoyant current-bin demand; minimum offered carbon among capacity-feasible assignments; otherwise minimum peak; no switching penalty. Diagnostic only.",
             "networks": {}, "runs": []}
    save_json(output / "manifest.json", study)
    rows = []
    for name in ("geant", "abilene"):
        cfg = config(root / ("configs/default.json" if name == "geant" else "configs/abilene.json"))
        data = load_prepared(root, cfg) if name == "geant" else abilene.load_prepared(root, cfg)
        folder = root / ("artifacts" if name == "geant" else "artifacts/abilene")
        models = predictors(root, data, cfg, folder)
        windows = validation_days(data, cfg, count)
        lo, hi = data.manifest["splits"]["validation"]
        if name == "geant":
            carbon = CarbonTable(root / "inputs/raw/carbon.csv")
            if carbon.source_hash != data.manifest["sources"]["carbon.csv"]["sha256"]:
                raise ValueError("GÉANT carbon source differs from prepared input")
            carbon_all, alignment = carbon.pair(data.times[lo:hi], cfg["carbon_years"][0])
            save_json(output / "geant_alignment.json", alignment)
            carbon_hash = carbon.source_hash
        else:
            annual = np.array([data.manifest["epa_annual_g_per_kwh"][code] for code in abilene.REGION])
            carbon_all = np.repeat(annual[None], hi-lo, axis=0)
            carbon_hash = data.manifest["sources"]["eGRID2004_aggregation.xls"]["sha256"]
        study["networks"][name] = {"config": cfg, "graph_hash": data.network.graph_hash,
                                   "traffic_sha256": data.manifest["traffic_sha256"],
                                   "carbon_sha256": carbon_hash,
                                   "predictor_sha256": {f: sha256(folder / f) for f in
                                                        ("gnn.pt", "gru.pt", "persistence.json")},
                                   "days": [str(data.times[a])[:10] for a, _ in windows]}
        for day, (start, stop) in enumerate(windows):
            for scenario in study["parameters"]["scenarios"]:
                seed = cfg["seed"] + day * 101
                rates = workload(data, cfg, start, stop, scenario, seed)
                traffic_hash = hashlib.sha256(rates[start-cfg["lookback"]:stop].tobytes()).hexdigest()
                ci = carbon_all[start-lo:stop-lo]
                cases: list[tuple[str, str, str, float]] = [("reactive_carbon", "reactive_carbon", "persistence", 0),
                         ("predictive_carbon", "predictive_carbon", "gnn", 0),
                         ("predictive_te", "predictive_te", "gnn", 0),
                         ("joint_gnn", "joint_gnn", "gnn", 0),
                         ("oracle_current_bin", "oracle_current_bin", "persistence", 0)]
                for budget in (0.0, 0.02):
                    for model in ("gnn", "gru", "persistence", "reactive"):
                        cases.append((f"tradeoff_{model}_{int(budget * 100):02d}",
                                      f"tradeoff_{model}",
                                      "persistence" if model == "reactive" else model, budget))
                for label, policy, model, budget in cases:
                    result = replay(data, cfg, rates, ci, start, stop, policy, models[model], 1, budget)
                    run_id = f"{name}_d{day}_{scenario}_{label}"
                    row = {"network": name, "window": day, "scenario": scenario,
                           "traffic_day": str(data.times[start])[:10], "seed": seed,
                           "traffic_sha256": traffic_hash, "carbon_budget_fraction": budget,
                           **result.summary, "policy": label}
                    path = output / "runs" / f"{run_id}.json"
                    save_json(path, {"summary": row, "records": result.records})
                    rows.append(row)
                    study["runs"].append({"run_id": run_id, "file": f"runs/{run_id}.json",
                                          "sha256": sha256(path), "traffic_sha256": traffic_hash})
                save_json(output / "manifest.json", study)
                print(f"Completed {name} validation day {day+1}/{count}, {scenario}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "summary.csv", index=False)
    metrics = ["forwarding_score", "served_fraction", "overload_minutes", "p95_utilization", "route_changes"]
    baseline = frame[frame.policy == "reactive_carbon"]
    joined = frame.merge(baseline, on=["network", "window", "scenario"], suffixes=("", "_reactive"),
                         validate="many_to_one")
    for metric in metrics:
        joined[f"delta_{metric}"] = joined[metric] - joined[f"{metric}_reactive"]
    cols = ["network", "window", "traffic_day", "scenario", "policy", "carbon_budget_fraction"]
    joined[cols + [f"delta_{metric}" for metric in metrics]].to_csv(output / "paired_differences.csv", index=False)
    study["summary_sha256"] = sha256(output / "summary.csv")
    study["paired_differences_sha256"] = sha256(output / "paired_differences.csv")
    study["status"] = "complete"
    save_json(output / "manifest.json", study)
    print(f"Saved {len(frame)} paired exploratory runs to {output}", flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")
    run(args.root.resolve(), args.output.resolve(), args.days)


if __name__ == "__main__":
    main()
