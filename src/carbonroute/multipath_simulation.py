"""Causal fractional replay; common OD fairness for split and unsplit routing."""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from .common import finite_nonnegative
from .data import Prepared
from .multipath import MultipathPlanner, Paths, fractional_service
from .prediction import Predictor
from .service import forwarding_score
from .service_first_simulation import replay as unsplit_replay

SINGLE_POLICIES = ("shortest_path", "reactive_carbon", "tradeoff_gnn",
                   "service_first_gnn", "service_first_persistence")
SPLIT_POLICIES = ("equal_split", "multipath_te_gnn", "multipath_carbon_gnn",
                  "multipath_carbon_persistence", "multipath_carbon_reactive",
                  "multipath_carbon_gnn_quantized")


def summarize(records: list[dict[str, Any]], cfg: dict, policy: str) -> dict:
    offered = sum(r["offered_mb"] for r in records)
    served = sum(r["served_mb"] for r in records)
    weighted = sum(r["carbon_weighted_mb"] for r in records)
    util = np.array([r["link_utilization"] for r in records])
    pair_offered = np.asarray([r["offered_mbps"] for r in records], dtype=float).sum(axis=0)
    pair_served = np.asarray([r["served_mbps"] for r in records], dtype=float).sum(axis=0)
    active = pair_offered > 0
    fractions = pair_served[active] / pair_offered[active]
    return {"policy": policy, "observation_delay_bins": 1, "bins": len(records),
            "offered_mb": offered, "served_mb": served, "served_fraction": served/offered if offered else 1.0,
            "carbon_weighted_mb": weighted, "forwarding_score": weighted/served if served else None,
            "max_utilization": float(util.max()), "p95_utilization": float(np.quantile(util, .95)),
            "overload_minutes": float(np.sum(util.max(axis=1) > 1+1e-9) * cfg["bin_seconds"] / 60),
            "excess_mbit": sum(r["excess_mbit"] for r in records),
            "route_changes": sum(r["changes"] for r in records),
            "redistributed_mass": sum(r["redistributed_mass"] for r in records),
            "mean_active_paths_per_pair": float(np.mean([r["active_paths_per_pair"] for r in records])),
            "min_pair_service_fraction": float(fractions.min()) if len(fractions) else None,
            "mean_served_path_delay_ms": sum(r["served_delay_mbps_ms"] for r in records) / pair_served.sum()
            if pair_served.sum() else None,
            "decision_ms_mean": float(np.mean([r["decision_ms"] for r in records])),
            "decision_ms_p95": float(np.quantile([r["decision_ms"] for r in records], .95)),
            "post_quantization_peak_violations": sum(r.get("quantization_peak_violation", False) for r in records)}


def replay(data: Prepared, cfg: dict, rates: np.ndarray, carbon: np.ndarray,
           start: int, stop: int, policy: str, predictor: Predictor) -> dict:
    if policy not in SINGLE_POLICIES + SPLIT_POLICIES:
        raise ValueError(f"Unknown multipath study policy: {policy}")
    lookback, horizon = cfg["lookback"], cfg["horizon"]
    if start < lookback or stop > len(rates) or stop <= start:
        raise ValueError("Invalid replay interval")
    if rates.shape != data.rates.shape or carbon.shape != (stop-start, data.network.node_count):
        raise ValueError("Replay shapes do not match data")
    finite_nonnegative(rates, "replay traffic")
    finite_nonnegative(carbon, "carbon")
    if np.any(rates[:, data.mask == 0] != 0) or not np.all(
            np.diff(data.times[start-lookback:stop]) == np.timedelta64(cfg["bin_seconds"], "s")):
        raise ValueError("Inactive demand or noncontiguous source times")
    paths = Paths(data.network, data.pairs, cfg)
    planner = MultipathPlanner(paths, cfg, carbon_aware=policy != "multipath_te_gnn",
                               buckets=100 if policy.endswith("quantized") else None)
    single = (unsplit_replay(data, cfg, rates, carbon, start, stop, policy, predictor, 1)
              if policy in SINGLE_POLICIES else None)
    records = []
    previous = planner.current.copy()
    senders = np.array([a for a, _ in data.network.arcs])
    for offset, k in enumerate(range(start, stop)):
        tick = time.perf_counter()
        evidence: dict[str, Any] = {}
        if single is not None:
            record = single.records[offset]
            weights = paths.one_hot(record["routes"])
            decision_ms = record["decision_ms"]
        elif policy == "equal_split":
            weights = 1 / (paths.membership.sum(axis=1)[paths.owners])
            decision_ms = (time.perf_counter()-tick)*1000
        else:
            history = rates[k-lookback:k].copy()
            history.setflags(write=False)
            forecast = (np.repeat(history[-1:], horizon, axis=0) if policy.endswith("reactive")
                        else predictor.predict(history) + predictor.margin)
            decision = planner.decide(forecast, carbon[offset].copy())
            weights = decision.weights
            decision_ms = (time.perf_counter()-tick)*1000
            evidence = {"projected_minimum_peak": decision.minimum_peak,
                        "projected_peak_limit": decision.peak_limit,
                        "projected_peak": decision.projected_peak,
                        "quantization_peak_violation": bool(policy.endswith("quantized") and
                                                            decision.projected_peak > decision.peak_limit + 1e-6)}
        # All fractions are committed before the target demand is accessed.
        effective = paths.effective(weights)
        demand = rates[k, [a for a, _ in data.pairs], [b for _, b in data.pairs]]
        served = fractional_service(demand, effective, data.network.capacities)
        if single is not None and not np.allclose(served, single.records[offset]["served_mbps"], atol=1e-8):
            raise AssertionError("Unsplit service differs under common fractional allocator")
        path_served = weights * served[paths.owners]
        offered_links = effective @ demand
        served_links = paths.incidence @ path_served
        if np.any(served_links > data.network.capacities + 1e-7):
            raise AssertionError("Realized service exceeds link capacity")
        costs = effective.T @ carbon[offset][senders]
        accounting = forwarding_score(served, costs, cfg["bin_seconds"])
        delta = np.abs(weights-previous)
        records.append({"step": offset, "traffic_time": str(data.times[k]),
                        "observed_through": str(data.times[k-1]), "carbon": carbon[offset].tolist(),
                        "offered_mbps": demand.tolist(), "served_mbps": served.tolist(),
                        "path_fractions": weights.tolist(), "path_served_mbps": path_served.tolist(),
                        "served_link_mbps": served_links.tolist(),
                        "link_utilization": (offered_links/data.network.capacities).tolist(),
                        "changes": int(np.sum(paths.membership @ delta > 1e-6)),
                        "redistributed_mass": float(delta.sum()/2),
                        "active_paths_per_pair": float(np.sum(weights > 1e-6)/len(data.pairs)),
                        "decision_ms": decision_ms,
                        "served_delay_mbps_ms": float(path_served @ paths.delays),
                        "offered_mb": float(demand.sum()*cfg["bin_seconds"]/8),
                        "excess_mbit": float(np.maximum(offered_links-data.network.capacities, 0).sum()*cfg["bin_seconds"]),
                        **accounting, **evidence})
        previous = weights.copy()
    return {"summary": summarize(records, cfg, policy), "records": records,
            "candidate_routes": [list(path) for path in paths.routes], "path_owners": paths.owners.tolist()}
