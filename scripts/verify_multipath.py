"""Reconstruct paired inputs and independently audit fractional flow accounting/fairness."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from carbonroute import abilene
from carbonroute.common import load_json, sha256
from carbonroute.data import CarbonTable
from carbonroute.experiments import workload
from carbonroute.followup_data import reference
from carbonroute.multipath import Paths
from carbonroute.service_first_experiment import input_data


def audit(root: Path, folder: Path) -> None:
    manifest = load_json(folder / "manifest.json")
    protocol = load_json(folder / "protocol.json")
    plan = load_json(folder / "evaluation_plan.json")
    if manifest["status"] != "complete":
        raise ValueError("Incomplete campaign")
    if (sha256(folder / "evaluation_plan.json") != manifest["evaluation_plan_sha256"] or
            sha256(folder / "protocol.json") != plan["protocol_sha256"]):
        raise ValueError("Changed frozen plan/protocol")
    for name, digest in plan["source_sha256"].items():
        if sha256(root / "src/carbonroute" / name) != digest:
            raise ValueError(f"Changed scientific source: {name}")
    for filename in ("summary.csv", "paired_differences.csv", "day_cluster_intervals.csv"):
        if sha256(folder / filename) != manifest[filename.removesuffix(".csv")+"_sha256"]:
            raise ValueError(f"Changed evidence: {filename}")
    summary = pd.read_csv(folder / "summary.csv")
    indexed = summary.set_index(["network", "window", "scenario", "policy"])
    if not indexed.index.is_unique or len(summary) != len(manifest["runs"]):
        raise ValueError("Duplicate or missing result")
    prepared, expected = {}, {}
    for name, evidence in plan["networks"].items():
        data, cfg, source = input_data(root, name, protocol)
        original, _, models = reference(root, name)
        if (source != evidence["source"] or original.manifest["traffic_sha256"] != evidence["reference_traffic_sha256"]
                or hashlib.sha256(data.rates.tobytes()).hexdigest() != evidence["prepared_rates_sha256"]):
            raise ValueError("Changed prepared/source traffic")
        for filename, digest in evidence["predictor_sha256"].items():
            if sha256(models / filename) != digest:
                raise ValueError("Changed reference model")
        carbon_path = root / ("inputs/raw/carbon.csv" if name == "geant" else "inputs/raw/eGRID2004_aggregation.xls")
        if sha256(carbon_path) != evidence["carbon_sha256"]:
            raise ValueError("Changed carbon source")
        if name == "geant":
            carbon, _ = CarbonTable(carbon_path).pair(data.times, 2022)
        else:
            annual = np.array([original.manifest["epa_annual_g_per_kwh"][code] for code in abilene.REGION])
            carbon = np.repeat(annual[None], len(data.times), axis=0)
        paths = Paths(data.network, data.pairs, cfg)
        if data.network.graph_hash != evidence["graph_hash"]:
            raise ValueError("Changed topology")
        prepared[name] = (data, cfg, paths)
        for day, stamp in enumerate(evidence["days"]):
            start = int(np.searchsorted(data.times, np.datetime64(stamp)))
            stop = start+86400//cfg["bin_seconds"]
            for scenario in protocol["workloads"]:
                rates = workload(data, cfg, start, stop, scenario, protocol["seed"]+day*101)
                digest = hashlib.sha256(rates[start-cfg["lookback"]:stop].tobytes()).hexdigest()
                offered = rates[start:stop, [a for a, _ in data.pairs], [b for _, b in data.pairs]]
                expected[name, day, scenario] = (offered, carbon[start:stop], data.times[start:stop], digest)
    sizes = summary.groupby(["network", "window", "scenario"])
    if len(sizes) != len(expected):
        raise ValueError("Missing paired workload")
    for _, group in sizes:
        if set(group.policy) != set(protocol["policies"]) or len(group) != len(protocol["policies"]):
            raise ValueError("Missing/duplicated declared policy")
    bins = 0
    for entry in manifest["runs"]:
        path = (folder / entry["file"]).resolve()
        if not path.is_relative_to((folder / "runs").resolve()) or sha256(path) != entry["sha256"]:
            raise ValueError("Invalid saved run path/checksum")
        run = load_json(path)
        row, records = run["summary"], run["records"]
        data, cfg, paths = prepared[row["network"]]
        offered_trace, carbon_trace, times, traffic_hash = expected[row["network"], row["window"], row["scenario"]]
        if row["traffic_sha256"] != traffic_hash or len(records) != len(times):
            raise ValueError("Unpaired or changed workload")
        if (run["candidate_routes"] != [list(route) for route in paths.routes] or
                run["path_owners"] != paths.owners.tolist()):
            raise ValueError("Changed candidate set")
        previous = paths.one_hot([options[0] for options in paths.candidates])
        total_mb = total_offered = total_weighted = overload = changes = redistributed = delay = 0.0
        offered_pairs, served_pairs = np.zeros(len(data.pairs)), np.zeros(len(data.pairs))
        all_util = []
        senders = np.array([a for a, _ in data.network.arcs])
        for k, record in enumerate(records):
            if record["traffic_time"] != str(times[k]) or record["observed_through"] >= record["traffic_time"]:
                raise ValueError("Noncausal timing")
            demand, ci = np.array(record["offered_mbps"]), np.array(record["carbon"])
            if not np.allclose(demand, offered_trace[k], atol=1e-9) or not np.allclose(ci, carbon_trace[k], atol=1e-9):
                raise ValueError("Realized input differs from verified source/workload")
            w, served = np.array(record["path_fractions"]), np.array(record["served_mbps"])
            paths.validate(w)
            effective = paths.effective(w)
            if np.any(served < -1e-8) or np.any(served > demand+1e-7):
                raise ValueError("Negative or invented service")
            path_offered, path_served = demand[paths.owners]*w, served[paths.owners]*w
            if not np.allclose(paths.membership @ path_offered, demand, atol=1e-7):
                raise ValueError("Offered traffic was dropped before overload accounting")
            if (not np.allclose(paths.membership @ path_served, served, atol=1e-7) or
                    not np.allclose(record["path_served_mbps"], path_served, atol=1e-7)):
                raise ValueError("Path/OD traffic conservation violated")
            actual_links = paths.incidence @ path_served
            if (np.any(actual_links > data.network.capacities+1e-7) or
                    not np.allclose(actual_links, record["served_link_mbps"], atol=1e-7)):
                raise ValueError("Link capacity/accounting violation")
            # Independent max-min certificate: every unsatisfied OD has a saturated
            # used link whose other users receive no higher total OD rate.
            saturated = actual_links >= data.network.capacities-1e-7
            for f in np.flatnonzero(served < demand-1e-7):
                blocked = [link for link in np.flatnonzero(saturated & (effective[:, f] > 1e-12))
                           if np.all(served[effective[link] > 1e-12] <= served[f]+1e-7)]
                if not blocked:
                    raise ValueError("Allocation lacks an OD max-min fairness certificate")
            util = paths.incidence @ path_offered / data.network.capacities
            if not np.allclose(util, record["link_utilization"], atol=1e-7):
                raise ValueError("Overload not computed from full offered traffic")
            mb = served.sum()*cfg["bin_seconds"]/8
            weighted = float(path_served @ (paths.incidence.T @ ci[senders]))*cfg["bin_seconds"]/8
            for key, value in (("served_mb", mb), ("carbon_weighted_mb", weighted)):
                if not np.isclose(record[key], value, atol=1e-7):
                    raise ValueError("Incorrect carbon/service accounting")
            delta = np.abs(w-previous)
            n_changes = int(np.sum(paths.membership @ delta > 1e-6))
            mass = float(delta.sum()/2)
            if record["changes"] != n_changes or not np.isclose(record["redistributed_mass"], mass):
                raise ValueError("Incorrect split-change accounting")
            if "projected_peak" in record:
                quantized = row["policy"].endswith("quantized")
                violated = record["projected_peak"] > record["projected_peak_limit"]+1e-6
                if (violated and not quantized) or (quantized and violated != record["quantization_peak_violation"]):
                    raise ValueError("Unreported planning guard violation")
                if quantized and not np.allclose(w*100, np.round(w*100), atol=1e-7):
                    raise ValueError("Quantized fractions do not use 100 buckets")
            total_mb += mb
            total_offered += demand.sum()*cfg["bin_seconds"]/8
            total_weighted += weighted
            overload += float(util.max() > 1+1e-9)*cfg["bin_seconds"]/60
            changes += n_changes
            redistributed += mass
            delay += float(path_served @ paths.delays)
            offered_pairs += demand
            served_pairs += served
            all_util.append(util)
            previous = w
            bins += 1
        active = offered_pairs > 0
        expected_summary = {"served_mb": total_mb, "offered_mb": total_offered,
            "carbon_weighted_mb": total_weighted, "overload_minutes": overload,
            "route_changes": changes, "redistributed_mass": redistributed,
            "served_fraction": total_mb/total_offered if total_offered else 1,
            "forwarding_score": total_weighted/total_mb if total_mb else None,
            "min_pair_service_fraction": float((served_pairs[active]/offered_pairs[active]).min()) if active.any() else None,
            "mean_served_path_delay_ms": delay/served_pairs.sum() if served_pairs.sum() else None,
            "p95_utilization": float(np.quantile(all_util, .95))}
        saved = indexed.loc[(row["network"], row["window"], row["scenario"], row["policy"])]
        for key, value in expected_summary.items():
            if value is None:
                if not pd.isna(saved[key]):
                    raise ValueError("Undefined score shown as a number")
            elif not np.isclose(saved[key], value, atol=1e-7, rtol=1e-8):
                raise ValueError(f"Incorrect summary: {entry['run_id']} {key}")
    evidence = {"runs": len(summary), "bins": bins, "paired_cases": len(expected),
                "checks": "Frozen sources/models, exact shared inputs, causal timing, path/OD conservation, full-offered overload, capacity, OD fairness certificates, carbon and summary accounting",
                "summary_sha256": sha256(folder / "summary.csv")}
    (folder / "AUDIT.json").write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
    print(f"Verified {len(summary)} runs / {bins} bins / {len(expected)} paired inputs, conservation and OD max-min fairness.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    audit(args.root.resolve(), args.folder.resolve())
