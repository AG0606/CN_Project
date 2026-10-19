"""Paired trace/carbon campaigns and window-clustered descriptive uncertainty."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import fingerprint, load_json, save_json, sha256
from .data import CarbonTable, Prepared, load_prepared
from .prediction import Persistence, TrainedPredictor
from .routing import JOINT_POLICIES, POLICIES
from .simulation import replay

MAIN_POLICIES = POLICIES[:4]


def evaluation_windows(data: Prepared, cfg: dict[str, Any], count: int,
                       split: str = "test") -> list[tuple[int, int]]:
    if split not in ("validation", "test"):
        raise ValueError("Evaluation split must be validation or test")
    lo, hi = data.manifest["splits"][split]
    candidates = []
    for start in range(lo+cfg["lookback"], hi-96+1):
        if data.times[start] != data.times[start].astype("datetime64[D]"):
            continue
        if np.all(np.diff(data.times[start-cfg["lookback"]:start+96]) == np.timedelta64(15, "m")):
            candidates.append((start, start+96))
    if len(candidates) < count:
        raise ValueError(f"Need {count} complete {split} days, found {len(candidates)}")
    return candidates[:count]


def workload(data: Prepared, cfg: dict[str, Any], start: int, stop: int,
             scenario: str, seed: int) -> np.ndarray:
    factor = cfg["congested_multiplier"] if scenario == "congested" else cfg["normal_multiplier"]
    rates = data.rates.copy()*factor
    if scenario == "bursty":
        rng = np.random.default_rng(seed)
        lo = start-cfg["lookback"]
        # Bursts are unannounced, per-flow events; their past portions become observable.
        for a, b in data.pairs:
            events = np.flatnonzero(rng.random(stop-lo) < cfg["burst_probability"]) + lo
            multiplier = np.ones(stop-lo)
            for k in events:
                multiplier[k-lo:min(k-lo+cfg["burst_bins"], stop-lo)] = cfg["burst_multiplier"]
            rates[lo:stop, a, b] *= multiplier
    elif scenario not in ("normal", "congested"):
        raise ValueError(f"Unknown scenario {scenario}")
    return rates


def paired_differences(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Cluster bootstrap over DAYS; carbon mappings of a day are not independent.

    Five windows yield preliminary, wide uncertainty, not publication-ready proof.
    Single-window pilots intentionally have no confidence interval.
    """
    metrics = ("forwarding_score", "served_fraction", "overload_minutes", "route_changes")
    rows = []
    for (scenario, delay), subset in frame.groupby(["scenario", "observation_delay_bins"]):
        baseline = subset[subset.policy == "reactive_carbon"]
        for policy in subset.policy.unique():
            if policy == "reactive_carbon":
                continue
            joined = subset[subset.policy == policy].merge(
                baseline, on=["window", "carbon_year"], suffixes=("", "_reactive"), validate="one_to_one")
            for metric in metrics:
                joined["difference"] = joined[metric]-joined[f"{metric}_reactive"]
                clusters = joined.groupby("window").difference.mean().to_numpy()
                if not len(clusters):
                    continue
                low = high = None
                if len(clusters) >= 2:
                    rng = np.random.default_rng(seed)
                    boot = rng.choice(clusters, (2000, len(clusters)), replace=True).mean(axis=1)
                    low, high = np.quantile(boot, [.025, .975]).tolist()
                rows.append({"policy": policy, "scenario": scenario, "observation_delay_bins": delay,
                             "metric": metric, "difference_vs_reactive": float(clusters.mean()),
                             "ci95_low": low, "ci95_high": high, "independent_day_clusters": len(clusters)})
    return pd.DataFrame(rows)


def campaign(root: Path, cfg: dict[str, Any], output: Path, paper: bool = False,
             overwrite: bool = False, split: str = "test", include_joint: bool = False,
             carbon_budget_fraction: float = 0.0) -> Path:
    if (output / "manifest.json").exists() and not overwrite:
        raise FileExistsError(f"Results already exist in {output}. Choose another --output or use --overwrite.")
    data = load_prepared(root, cfg)
    carbon = CarbonTable(root / "inputs/raw/carbon.csv")
    expected_carbon = data.manifest["sources"]["carbon.csv"]["sha256"]
    if carbon.source_hash != expected_carbon:
        raise ValueError("Carbon input changed after preparation")
    gnn = TrainedPredictor(root / "artifacts", data, cfg)
    gru = TrainedPredictor(root / "artifacts", data, cfg, "gru") if include_joint else None
    persist_meta = load_json(root / "artifacts/persistence.json")
    if persist_meta["config_hash"] != fingerprint(cfg) or persist_meta["traffic_sha256"] != data.manifest["traffic_sha256"]:
        raise ValueError("Persistence margin does not match this data/configuration")
    persistence = Persistence(cfg["horizon"], data.mask, np.array(persist_meta["margin_mbps"]))
    day_count = (7 if split == "validation" else 5) if paper else 1
    windows = evaluation_windows(data, cfg, day_count, split)
    years = cfg["carbon_years"] if paper else cfg["carbon_years"][:1]
    scenarios = ("normal", "congested", "bursty") if paper else ("normal", "congested")
    delays = (1, 0) if paper and not include_joint else (1,)
    output.mkdir(parents=True, exist_ok=True)
    run_folder = output / "runs"
    run_folder.mkdir(exist_ok=True)
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": ("joint-development" if split == "validation" else
                 "joint-test-exploratory" if paper else "joint-test-pilot") if include_joint
                else ("paper" if paper else "pilot"),
        "evaluation_split": split, "include_joint": include_joint,
        "carbon_budget_fraction": carbon_budget_fraction,
        "status": "running",
        "config": cfg, "config_hash": fingerprint(cfg), "source_revision": revision,
        "source_files": {str(p.relative_to(root)).replace("\\", "/"): sha256(p)
                         for p in sorted((root / "src/carbonroute").glob("*")) if p.is_file()},
        "graph": data.network.metadata(), "graph_hash": data.network.graph_hash,
        "traffic_manifest": data.manifest, "checkpoint_sha256": sha256(root / "artifacts/gnn.pt"),
        "checkpoint_sha256_by_model": {
            "gnn": sha256(root / "artifacts/gnn.pt"),
            "gru": sha256(root / "artifacts/gru.pt"),
            "persistence": sha256(root / "artifacts/persistence.json"),
        } if include_joint else {},
        "carbon_sha256": carbon.source_hash, "python": platform.python_version(),
        "platform": platform.platform(), "runs": [], "failed_runs": [],
        "alignment_sha256": {},
        "interpretation": "Constructed scenario: 2005 traffic and later daily country carbon; aggregate service, no packet or physical energy measurements",
        "power_sensitivity": {"idle_only": {"idle_w": 50, "beta_w_per_mbps": 0},
                              "idle_dominated": {"idle_w": 50, "beta_w_per_mbps": .1},
                              "load_sensitive": {"idle_w": 5, "beta_w_per_mbps": 1}},
    }
    # Freeze forecast evidence with this campaign so later retraining cannot change its report.
    for name in ("forecast_metrics.csv", "training_summary.json"):
        shutil.copyfile(root / "artifacts" / name, output / name)
    manifest["forecast_metrics_sha256"] = sha256(output / "forecast_metrics.csv")
    manifest["training_summary_sha256"] = sha256(output / "training_summary.json")
    save_json(output / "manifest.json", manifest)
    lo, hi = data.manifest["splits"][split]
    carbon_cache = {}
    for year in years:
        ci, alignment = carbon.pair(data.times[lo:hi], year)
        carbon_cache[year] = ci
        alignment_path = output / f"alignment_{year}.json"
        save_json(alignment_path, alignment)
        manifest["alignment_sha256"][str(year)] = sha256(alignment_path)
    summaries = []
    started = time.perf_counter()
    for window_id, (start, stop) in enumerate(windows):
        for scenario in scenarios:
            seed = cfg["seed"] + window_id * 101
            rates = workload(data, cfg, start, stop, scenario, seed)
            traffic_hash = hashlib.sha256(rates[start-cfg["lookback"]:stop].tobytes()).hexdigest()
            for year in years:
                ci = carbon_cache[year][start-lo:stop-lo]
                for delay in delays:
                    policies = (POLICIES + JOINT_POLICIES if include_joint else POLICIES) if delay == 1 else MAIN_POLICIES
                    for policy in policies:
                        run_id = f"w{window_id}_{year}_{scenario}_lag{delay}_{policy}"
                        fields = {"run_id": run_id, "window": window_id, "scenario": scenario,
                                  "carbon_year": year, "seed": seed, "start": start, "stop": stop,
                                  "traffic_start": str(data.times[start]), "traffic_sha256": traffic_hash}
                        try:
                            predictor = (persistence if policy in ("persistence_carbon", "joint_persistence")
                                         else gru if policy == "joint_gru" else gnn)
                            assert predictor is not None
                            result = replay(data, cfg, rates, ci, start, stop, policy, predictor, delay,
                                            carbon_budget_fraction)
                            summary = {**fields, **result.summary}
                            run_path = run_folder / f"{run_id}.json"
                            save_json(run_path, {"summary": summary, "records": result.records})
                            summaries.append(summary)
                            manifest["runs"].append({**fields, "policy": policy, "observation_delay_bins": delay,
                                                     "file": f"runs/{run_id}.json", "sha256": sha256(run_path)})
                        except Exception as exc:
                            manifest["status"] = "failed"
                            manifest["failed_runs"].append({**fields, "error": repr(exc)})
                            save_json(output / "manifest.json", manifest)
                            raise
            print(f"Completed window {window_id+1}/{len(windows)}, {scenario}; {len(summaries)} paired runs", flush=True)
    manifest["runtime_seconds"] = time.perf_counter()-started
    frame = pd.DataFrame(summaries)
    frame.to_csv(output / "summary.csv", index=False)
    paired_differences(frame, cfg["seed"]).to_csv(output / "paired_differences.csv", index=False)
    manifest["summary_sha256"] = sha256(output / "summary.csv")
    manifest["status"] = "complete"
    save_json(output / "manifest.json", manifest)
    print(f"Saved {len(frame)} runs in {manifest['runtime_seconds']:.1f}s to {output}", flush=True)
    return output
