"""Audit multi-seed lineage, shared capacity scenarios and explicitly clairvoyant controls."""
import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from carbonroute import abilene
from carbonroute.common import load_json, save_json, sha256
from carbonroute.data import CarbonTable
from carbonroute.experiments import workload
from carbonroute.final_validation import capacity_data, cases
from carbonroute.followup_data import reference
from carbonroute.multipath import Paths
from carbonroute.service_first_experiment import input_data


def audit(root: Path, folder: Path) -> None:
    manifest = load_json(folder / "manifest.json")
    protocol = load_json(folder / "protocol.json")
    plan = load_json(folder / "evaluation_plan.json")
    if manifest["status"] != "complete":
        raise ValueError("Incomplete final validation")
    if (sha256(folder / "evaluation_plan.json") != manifest["evaluation_plan_sha256"] or
            sha256(folder / "protocol.json") != plan["protocol_sha256"]):
        raise ValueError("Changed frozen protocol or evaluation plan")
    for name, digest in plan["source_sha256"].items():
        if sha256(root / "src/carbonroute" / name) != digest:
            raise ValueError(f"Changed scientific source: {name}")
    for filename in ("summary.csv", "forecast_metrics.csv", "day_cluster_intervals.csv"):
        if sha256(folder / filename) != manifest[filename.removesuffix(".csv")+"_sha256"]:
            raise ValueError("Changed outcome evidence")
    frame = pd.read_csv(folder / "summary.csv")
    index_keys = ["network", "window", "scenario", "capacity_factor", "policy", "model_seed"]
    indexed = frame.set_index(index_keys)
    if not indexed.index.is_unique or len(frame) != len(manifest["runs"]):
        raise ValueError("Duplicate/missing saved outcome")
    expected, geometries = {}, {}
    checkpoints = 0
    for name, evidence in plan["networks"].items():
        original, cfg, _ = reference(root, name)
        gate = dict(protocol, test_days=protocol["test_days"]+1) if name == "geant" else protocol
        data, _, source = input_data(root, name, gate)
        if (source != evidence["source"] or original.manifest["traffic_sha256"] != evidence["reference_traffic_sha256"] or
                hashlib.sha256(data.rates.tobytes()).hexdigest() != evidence["prepared_rates_sha256"]):
            raise ValueError("Changed traffic or reference transforms")
        for seed in protocol["model_seeds"]:
            directory = root / "artifacts/final-validation" / name / str(seed)
            training = load_json(directory / "training_summary.json")
            if training["test_evaluated"] is not False or training["config"]["seed"] != seed:
                raise ValueError("Training used test evaluation or wrong seed")
            metrics = pd.read_csv(directory / "forecast_metrics.csv")
            if set(metrics.split) != {"validation"}:
                raise ValueError("Training artifacts include final-test outcomes")
            for filename, digest in evidence["models"][str(seed)].items():
                if sha256(directory / filename) != digest:
                    raise ValueError("Changed trained evidence")
            for kind in ("gnn", "gru"):
                meta = load_json(directory / f"{kind}.json")
                if meta["traffic_sha256"] != original.manifest["traffic_sha256"] or meta["seed"] != seed:
                    raise ValueError("Wrong model lineage")
                checkpoints += 1
        carbon_path = root / ("inputs/raw/carbon.csv" if name == "geant" else "inputs/raw/eGRID2004_aggregation.xls")
        if sha256(carbon_path) != evidence["carbon_sha256"]:
            raise ValueError("Changed carbon input")
        if name == "geant":
            carbon, _ = CarbonTable(carbon_path).pair(data.times, 2022)
        else:
            annual = np.array([original.manifest["epa_annual_g_per_kwh"][code] for code in abilene.REGION])
            carbon = np.repeat(annual[None], len(data.times), axis=0)
        for factor in protocol["capacity_factors"]:
            modified, settings = capacity_data(data, cfg, factor)
            geometries[name, factor] = (Paths(modified.network, modified.pairs, settings), settings)
        for day, stamp in enumerate(evidence["days"]):
            start = int(np.searchsorted(data.times, np.datetime64(stamp)))
            stop = start+86400//cfg["bin_seconds"]
            for scenario in protocol["workloads"]:
                rates = workload(data, cfg, start, stop+cfg["horizon"]-1, scenario, protocol["workload_seed"]+day*101)
                digest = hashlib.sha256(rates[start-cfg["lookback"]:stop+cfg["horizon"]-1].tobytes()).hexdigest()
                demand = rates[start:stop, [a for a, _ in data.pairs], [b for _, b in data.pairs]]
                expected[name, day, scenario] = (demand, carbon[start:stop], data.times[start:stop+cfg["horizon"]-1], digest)
    groups = frame.groupby(["network", "window", "scenario", "capacity_factor"])
    if len(groups) != len(expected)*len(protocol["capacity_factors"]):
        raise ValueError("Missing capacity/scenario group")
    for (_, _, _, factor), rows in groups:
        declared = {(label, seed) for label, _, _, seed, _, _ in cases(protocol, factor)}
        if set(zip(rows.policy, rows.model_seed)) != declared or len(rows) != len(declared):
            raise ValueError("Missing a seed, diagnostic or matched policy")
    bins, perfect_runs = 0, 0
    for number, entry in enumerate(manifest["runs"]):
        path = (folder / entry["file"]).resolve()
        if not path.is_relative_to((folder / "runs").resolve()) or sha256(path) != entry["sha256"]:
            raise ValueError("Invalid run path or changed log")
        run = load_json(path)
        row, records = run["summary"], run["records"]
        paths, cfg = geometries[row["network"], row["capacity_factor"]]
        offered_trace, carbon_trace, times, digest = expected[row["network"], row["window"], row["scenario"]]
        if digest != row["traffic_sha256"] or len(records) != len(offered_trace):
            raise ValueError("Changed/unpaired workload")
        declared = next(item for item in cases(protocol, row["capacity_factor"])
                        if item[0] == row["policy"] and item[3] == row["model_seed"])
        perfect = declared[4]
        if row["future_demand_diagnostic"] != perfect or row["zero_margin"] != declared[5]:
            raise ValueError("Mislabeled forecast or future-demand control")
        perfect_runs += int(perfect)
        if run["candidate_routes"] != [list(route) for route in paths.routes] or run["path_owners"] != paths.owners.tolist():
            raise ValueError("Different candidate paths")
        if row["capacity_mbps"] != paths.network.capacity_mbps:
            raise ValueError("Different capacity assumption")
        previous = paths.one_hot([options[0] for options in paths.candidates])
        totals = {key: 0.0 for key in ("served_mb", "offered_mb", "carbon_weighted_mb", "overload_minutes", "route_changes", "redistributed_mass")}
        offered_pairs, served_pairs = np.zeros(len(paths.pairs)), np.zeros(len(paths.pairs))
        all_util, delay = [], 0.0
        senders = np.array([a for a, _ in paths.network.arcs])
        for k, record in enumerate(records):
            required_time = str(times[k+cfg["horizon"]-1]) if perfect else str(times[k]-np.timedelta64(cfg["bin_seconds"], "s"))
            # Normalize numpy timestamp resolution before comparing canonical minute strings.
            required_time = str(np.datetime64(required_time, "m"))
            if (record["traffic_time"] != str(times[k]) or record["observed_through"] != required_time or
                    record["future_demand_diagnostic"] != perfect):
                raise ValueError("Incorrect causal/clairvoyant observation timing")
            demand, ci = np.array(record["offered_mbps"]), np.array(record["carbon"])
            if not np.array_equal(demand, offered_trace[k]) or not np.array_equal(ci, carbon_trace[k]):
                raise ValueError("Different realized source input")
            w, served = np.array(record["path_fractions"]), np.array(record["served_mbps"])
            paths.validate(w)
            effective = paths.effective(w)
            if (served < -1e-8).any() or (served > demand+1e-7).any():
                raise ValueError("Invented/negative service")
            path_offered, path_served = demand[paths.owners]*w, served[paths.owners]*w
            links = paths.incidence @ path_served
            if (not np.allclose(paths.membership @ path_offered, demand, atol=1e-7) or
                    not np.allclose(paths.membership @ path_served, served, atol=1e-7) or
                    not np.allclose(path_served, record["path_served_mbps"], atol=1e-7) or
                    not np.allclose(links, record["served_link_mbps"], atol=1e-7) or
                    (links > paths.network.capacities+1e-7).any()):
                raise ValueError("Traffic conservation or capacity failure")
            saturated = links >= paths.network.capacities-1e-7
            for f in np.flatnonzero(served < demand-1e-7):
                if not any(np.all(served[effective[link] > 1e-12] <= served[f]+1e-7)
                           for link in np.flatnonzero(saturated & (effective[:, f] > 1e-12))):
                    raise ValueError("Per-OD max-min fairness certificate missing")
            util = paths.incidence @ path_offered/paths.network.capacities
            if not np.allclose(util, record["link_utilization"], atol=1e-7):
                raise ValueError("Offered overload accounting changed")
            served_mb = served.sum()*cfg["bin_seconds"]/8
            # The replay sums source demand in its native dtype (float32 for GÉANT).
            # Reproduce that rounding, then separately bound its float64 discrepancy.
            offered_mb = float(offered_trace[k].sum()*cfg["bin_seconds"]/8)
            exact_offered_mb = float(demand.sum()*cfg["bin_seconds"]/8)
            precision = np.finfo(offered_trace.dtype).eps
            if (not np.isclose(record["offered_mb"], offered_mb, atol=1e-9, rtol=1e-12) or
                    abs(offered_mb-exact_offered_mb) > 4*precision*max(1, exact_offered_mb)):
                raise ValueError("Incorrect offered bytes beyond native-dtype rounding")
            carbon_weighted = float(path_served @ (paths.incidence.T @ ci[senders]))*cfg["bin_seconds"]/8
            if not np.isclose(record["served_mb"], served_mb) or not np.isclose(record["carbon_weighted_mb"], carbon_weighted):
                raise ValueError("Incorrect carbon/byte accounting")
            delta = np.abs(w-previous)
            changed = int(np.sum(paths.membership @ delta > 1e-6))
            mass = float(delta.sum()/2)
            if record["changes"] != changed or not np.isclose(record["redistributed_mass"], mass):
                raise ValueError("Incorrect churn accounting")
            totals["served_mb"] += served_mb
            totals["offered_mb"] += offered_mb
            totals["carbon_weighted_mb"] += carbon_weighted
            totals["overload_minutes"] += float(util.max() > 1+1e-9)*cfg["bin_seconds"]/60
            totals["route_changes"] += changed
            totals["redistributed_mass"] += mass
            delay += float(path_served @ paths.delays)
            offered_pairs += demand
            served_pairs += served
            all_util.append(util)
            previous = w
            bins += 1
        saved = indexed.loc[tuple(row[key] for key in index_keys)]
        values = {**totals, "served_fraction": totals["served_mb"]/totals["offered_mb"] if totals["offered_mb"] else 1,
                  "forwarding_score": totals["carbon_weighted_mb"]/totals["served_mb"] if totals["served_mb"] else None,
                  "p95_utilization": float(np.quantile(all_util, .95)),
                  "min_pair_service_fraction": float((served_pairs[offered_pairs > 0]/offered_pairs[offered_pairs > 0]).min()) if (offered_pairs > 0).any() else None,
                  "mean_served_path_delay_ms": delay/served_pairs.sum() if served_pairs.sum() else None}
        for key, value in values.items():
            if value is None:
                if not pd.isna(saved[key]):
                    raise ValueError("Undefined metric shown as a number")
            elif not np.isclose(saved[key], value, atol=1e-7, rtol=1e-8):
                raise ValueError(f"Incorrect summary {entry['run_id']}: {key}")
        if (number+1) % 300 == 0:
            print(f"Audited {number+1}/{len(manifest['runs'])} runs", flush=True)
    forecast = pd.read_csv(folder / "forecast_metrics.csv")
    for name, selected in forecast.groupby("network"):
        for kind in ("gnn", "gru"):
            if set(selected[selected.model == kind].model_seed) != set(protocol["model_seeds"]):
                raise ValueError("Missing a forecast seed")
    save_json(folder / "AUDIT.json", {"runs": len(frame), "bins": bins, "new_checkpoints": checkpoints,
              "explicit_future_demand_runs": perfect_runs, "causal_runs": len(frame)-perfect_runs,
              "checks": "Frozen model/source lineage, validation-only training, declared seeds/regimes, exact shared inputs, causal vs future-aware labels, per-OD fairness, conservation, capacity, carbon and metric accounting",
              "summary_sha256": sha256(folder / "summary.csv")})
    print(f"Verified final validation: {len(frame)} runs, {bins} bins, {checkpoints} checkpoints, {perfect_runs} explicitly clairvoyant diagnostics.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    audit(args.root.resolve(), args.folder.resolve())
