"""Three focused checks: seeds, capacity regimes, identical planners with perfect demand."""
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
from .data import CarbonTable, Prepared
from .experiments import workload
from .followup_data import reference
from .multipath_simulation import replay
from .network import Network
from .prediction import TrainedPredictor, batch_prediction, forecast_metrics, train
from .service_first_experiment import input_data


class SequenceForecast:
    """Replay cached forecasts, asserting the observed history matches each index."""
    def __init__(self, history: np.ndarray, forecasts: np.ndarray, margin: np.ndarray):
        if len(history) != len(forecasts):
            raise ValueError("History/forecast length mismatch")
        self.history, self.forecasts, self.margin = history, forecasts, margin
        self.cursor = 0

    def predict(self, history: np.ndarray) -> np.ndarray:
        k = self.cursor
        if k >= len(self.history) or not np.array_equal(history, self.history[k]):
            raise ValueError("Cached prediction does not match observed history")
        self.cursor += 1
        return self.forecasts[k].copy()


def capacity_data(data: Prepared, cfg: dict, factor: float) -> tuple[Prepared, dict]:
    graph = data.network
    network = Network(graph.coordinates, graph.physical_edges, graph.source_link_ids,
                      graph.capacity_mbps*factor, graph.fiber_stretch, graph.router_delay_ms,
                      graph.node_ids, graph.countries)
    modified = dict(cfg, capacity_mbps=network.capacity_mbps)
    return Prepared(data.times, data.rates, data.mask, data.scale, network, data.pairs, data.manifest), modified


def cases(protocol: dict, factor: int) -> list[tuple[str, str, str, int, bool, bool]]:
    # label, existing replay engine, predictor family, seed, perfect, zero_margin
    result = []
    for label in protocol["base_policies"]:
        family = "gru" if label.endswith("gru") else "gnn" if label.endswith("gnn") else "persistence"
        engine = label.replace("_gru", "_gnn")
        result.append((label, engine, family, 42 if family != "persistence" else -1, False, False))
    if factor == 1:
        for seed in protocol["model_seeds"]:
            if seed == 42:
                continue
            for planner in ("service_first", "multipath_carbon"):
                for family in ("gnn", "gru"):
                    result.append((f"{planner}_{family}", f"{planner}_gnn", family, seed, False, False))
        for planner in ("service_first", "multipath_carbon"):
            result.append((f"{planner}_gnn_no_margin", f"{planner}_gnn", "gnn", 42, False, True))
    for label, engine in (("perfect_service_first", "service_first_gnn"),
                          ("perfect_multipath_carbon", "multipath_carbon_gnn"),
                          ("perfect_multipath_te", "multipath_te_gnn")):
        result.append((label, engine, "perfect", -1, True, True))
    return result


def training(root: Path, protocol: dict) -> None:
    for name in ("geant", "abilene"):
        data, base, _ = reference(root, name)
        for seed in protocol["model_seeds"]:
            cfg = dict(base, seed=seed)
            folder = root / "artifacts/final-validation" / name / str(seed)
            if (folder / "training_summary.json").exists():
                if load_json(folder / "training_summary.json").get("test_evaluated") is not False:
                    raise ValueError("Final-test evaluation present in training artifacts")
                for kind in ("gnn", "gru"):
                    TrainedPredictor(folder, data, cfg, kind)
                print(f"Reusing trained {name} seed {seed}", flush=True)
            else:
                print(f"Training {name} seed {seed}, validation-only selection", flush=True)
                train(root, cfg, data, folder, evaluate_test=False)


def clustered(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (network, factor, scenario), group in frame.groupby(["network", "capacity_factor", "scenario"]):
        reference_rows = group[group.policy == "reactive_carbon"]
        for policy, selected in group.groupby("policy", sort=False):
            if policy == "reactive_carbon":
                continue
            joined = selected.merge(reference_rows, on="window", suffixes=("", "_baseline"), validate="many_to_one")
            for metric in ("forwarding_score", "served_fraction", "overload_minutes", "route_changes"):
                joined["difference"] = joined[metric]-joined[metric+"_baseline"]
                values = joined.groupby("window").difference.mean().dropna().to_numpy()
                if not len(values):
                    continue
                bootstrap = np.random.default_rng(42).choice(values, (2000, len(values)), replace=True).mean(axis=1)
                lo, hi = np.quantile(bootstrap, [.025, .975])
                rows.append({"network": network, "capacity_factor": factor, "scenario": scenario,
                             "policy": policy, "metric": metric, "mean_difference": float(values.mean()),
                             "ci95_low": float(lo), "ci95_high": float(hi), "day_clusters": len(values)})
    return pd.DataFrame(rows)


def run(root: Path, output: Path) -> None:
    source_protocol = root / "configs/final_validation_protocol.json"
    protocol = load_json(source_protocol)
    output.mkdir(parents=True, exist_ok=True)
    frozen = output / "protocol.json"
    if frozen.exists() and sha256(frozen) != sha256(source_protocol):
        raise ValueError("Changed frozen protocol")
    if not frozen.exists():
        frozen.write_bytes(source_protocol.read_bytes())
        save_json(output / "protocol_record.json", {"protocol_sha256": sha256(frozen),
                  "frozen_utc": datetime.now(timezone.utc).isoformat(), "note": "Before training and new test outcomes"})
    training(root, protocol)
    science = ("final_validation.py", "multipath.py", "multipath_simulation.py", "service_first_experiment.py",
               "service_first.py", "service_first_simulation.py", "routing.py", "simulation.py", "service.py",
               "data.py", "prediction.py", "network.py", "common.py", "experiments.py", "abilene.py", "followup_data.py")
    plan: dict[str, Any] = {"protocol_sha256": sha256(frozen), "networks": {},
        "source_sha256": {name: sha256(Path(__file__).with_name(name)) for name in science},
        "environment": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                         for name in ("numpy", "scipy", "torch", "pandas")}}}
    loaded = {}
    for name in ("geant", "abilene"):
        input_protocol = dict(protocol, test_days=protocol["test_days"]+1) if name == "geant" else protocol
        data, cfg, source = input_data(root, name, input_protocol)
        original, _, _ = reference(root, name)
        models, model_evidence = {}, {}
        for seed in protocol["model_seeds"]:
            folder = root / "artifacts/final-validation" / name / str(seed)
            for kind in ("gnn", "gru"):
                models[kind, seed] = TrainedPredictor(folder, original, dict(cfg, seed=seed), kind)
            model_evidence[str(seed)] = {f: sha256(folder / f) for f in
                                         ("gnn.pt", "gnn.json", "gru.pt", "gru.json", "persistence.json", "training_summary.json")}
        persistence = load_json(root / "artifacts/final-validation" / name / "42/persistence.json")
        day0 = np.datetime64(protocol[f"{name}_start"])
        bins, horizon = 86400//cfg["bin_seconds"], cfg["horizon"]
        windows = []
        for day in range(protocol["test_days"]):
            stamp = day0+np.timedelta64(day, "D")
            start = int(np.searchsorted(data.times, stamp))
            stop = start+bins
            if (start < cfg["lookback"] or stop+horizon-1 > len(data.times) or data.times[start] != stamp or
                    not np.all(np.diff(data.times[start-cfg["lookback"]:stop+horizon-1]) ==
                               np.timedelta64(cfg["bin_seconds"], "s"))):
                raise ValueError(f"Unavailable predeclared replay/label day: {name} {stamp}")
            windows.append((start, stop))
        carbon_path = root / ("inputs/raw/carbon.csv" if name == "geant" else "inputs/raw/eGRID2004_aggregation.xls")
        if sha256(carbon_path) != original.manifest["sources"][carbon_path.name]["sha256"]:
            raise ValueError("Changed carbon source")
        if name == "geant":
            carbon, alignment = CarbonTable(carbon_path).pair(data.times, 2022)
            save_json(output / "geant_alignment.json", alignment)
        else:
            annual = np.array([original.manifest["epa_annual_g_per_kwh"][code] for code in abilene.REGION])
            carbon = np.repeat(annual[None], len(data.times), axis=0)
        plan["networks"][name] = {"config": cfg, "source": source, "models": model_evidence,
            "reference_traffic_sha256": original.manifest["traffic_sha256"], "graph_hash": data.network.graph_hash,
            "prepared_rates_sha256": hashlib.sha256(data.rates.tobytes()).hexdigest(), "carbon_sha256": sha256(carbon_path),
            "days": [str(data.times[a])[:10] for a, _ in windows],
            "capacity_mbps": [data.network.capacity_mbps*f for f in protocol["capacity_factors"]]}
        loaded[name] = (data, original, cfg, models, persistence, windows, carbon)
    path = output / "evaluation_plan.json"
    if path.exists() and load_json(path) != plan:
        raise ValueError("Changed scientific source, inputs or checkpoints after evaluation freeze")
    if not path.exists():
        save_json(path, plan)
    manifest_path = output / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {
        "status": "running", "evaluation_plan_sha256": sha256(path), "networks": plan["networks"], "runs": []}
    if manifest["evaluation_plan_sha256"] != sha256(path):
        raise ValueError("Changed evaluation plan")
    if manifest["status"] == "complete":
        for filename in ("summary.csv", "forecast_metrics.csv", "day_cluster_intervals.csv"):
            if sha256(output / filename) != manifest[filename.removesuffix(".csv")+"_sha256"]:
                raise ValueError("Changed completed evidence")
        print("Reusing checksum-verified final validation", flush=True)
        return
    (output / "runs").mkdir(exist_ok=True)
    existing = {entry["run_id"]: entry for entry in manifest["runs"]}
    rows: list[dict[str, Any]] = []
    forecast_rows: list[dict[str, Any]] = []
    for name, (data, original, cfg, models, persistence, windows, carbon) in loaded.items():
        # Raw normal source-scaled forecast evaluation on all seven replay-day starts.
        indices = [k for start, stop in windows for k in range(start, stop)]
        x = np.stack([data.rates[k-cfg["lookback"]:k] for k in indices])
        y = np.stack([data.rates[k:k+cfg["horizon"]] for k in indices])
        lo, hi = original.manifest["splits"]["train"]
        threshold = float(np.quantile(original.rates[lo:hi, original.mask.astype(bool)], .9))
        for (kind, seed), model in models.items():
            prediction = batch_prediction(model.model, x, model.scale, cfg["batch_size"])
            forecast_rows.extend({"network": name, "model": kind, "model_seed": seed, **metric} for metric in
                                 forecast_metrics(y, prediction, model.margin, data.mask, threshold))
        persistent_margin = np.array(persistence["margin_mbps"])
        forecast_rows.extend({"network": name, "model": "persistence", "model_seed": -1, **metric} for metric in
                             forecast_metrics(y, np.repeat(x[:, -1:], cfg["horizon"], axis=1), persistent_margin,
                                              data.mask, threshold))
        del x, y
        for day, (start, stop) in enumerate(windows):
            for scenario in protocol["workloads"]:
                seed = protocol["workload_seed"]+day*101
                rates = workload(data, cfg, start, stop+cfg["horizon"]-1, scenario, seed)
                traffic_hash = hashlib.sha256(rates[start-cfg["lookback"]:stop+cfg["horizon"]-1].tobytes()).hexdigest()
                histories = np.stack([rates[k-cfg["lookback"]:k] for k in range(start, stop)])
                future = np.stack([rates[k:k+cfg["horizon"]] for k in range(start, stop)])
                forecasts = {key: batch_prediction(model.model, histories, model.scale, cfg["batch_size"])
                             for key, model in models.items()}
                persist_forecast = np.repeat(histories[:, -1:], cfg["horizon"], axis=1)
                for factor in protocol["capacity_factors"]:
                    modified, settings = capacity_data(data, cfg, factor)
                    for label, engine, family, model_seed, perfect, no_margin in cases(protocol, factor):
                        run_id = f"{name}_d{day}_{scenario}_c{factor}_{label}_s{model_seed}"
                        run_path = output / "runs" / f"{run_id}.json"
                        if run_id in existing:
                            if sha256(run_path) != existing[run_id]["sha256"]:
                                raise ValueError("Changed saved run")
                            rows.append(load_json(run_path)["summary"])
                            continue
                        if run_path.exists():
                            raise ValueError("Unmanifested saved run")
                        values = future if perfect else persist_forecast if family == "persistence" else forecasts[family, model_seed]
                        margin = (np.zeros_like(persistent_margin) if no_margin else persistent_margin if family == "persistence"
                                  else models[family, model_seed].margin)
                        predictor = SequenceForecast(histories, values, margin)
                        result = replay(modified, settings, rates, carbon[start:stop], start, stop, engine, predictor)
                        for offset, record in enumerate(result["records"]):
                            record["future_demand_diagnostic"] = perfect
                            if perfect:
                                record["observed_through"] = str(data.times[start+offset+cfg["horizon"]-1])
                        row = {"network": name, "window": day, "traffic_day": str(data.times[start])[:10],
                               "scenario": scenario, "capacity_factor": factor, "capacity_mbps": settings["capacity_mbps"],
                               "model_seed": model_seed, "predictor_family": family, "future_demand_diagnostic": perfect,
                               "zero_margin": no_margin, "traffic_sha256": traffic_hash, **result["summary"], "policy": label}
                        result["summary"] = row
                        save_json(run_path, result)
                        rows.append(row)
                        manifest["runs"].append({"run_id": run_id, "file": f"runs/{run_id}.json", "sha256": sha256(run_path)})
                        save_json(manifest_path, manifest)
                    print(f"Completed final {name} day {day+1}/7, {scenario}, capacity x{factor}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "summary.csv", index=False)
    pd.DataFrame(forecast_rows).to_csv(output / "forecast_metrics.csv", index=False)
    clustered(frame).to_csv(output / "day_cluster_intervals.csv", index=False)
    for filename in ("summary.csv", "forecast_metrics.csv", "day_cluster_intervals.csv"):
        manifest[filename.removesuffix(".csv")+"_sha256"] = sha256(output / filename)
    manifest["status"] = "complete"
    save_json(manifest_path, manifest)
    print(f"Saved {len(frame)} final-validation runs", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "results/final-validation-20261027")
    args = parser.parse_args()
    run(args.root.resolve(), args.output.resolve())
