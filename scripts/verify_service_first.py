"""Audit paired service-first study, causal timing, accounting and frozen lineage."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from verify_tradeoff import verify

from carbonroute.common import load_json, sha256
from carbonroute.followup_data import reference
from carbonroute.service import progressive_fill


def audit(root: Path, folder: Path) -> None:
    verify(folder)
    plan = load_json(folder / "evaluation_plan.json")
    protocol = load_json(folder / "protocol.json")
    manifest = load_json(folder / "manifest.json")
    if (sha256(folder / "protocol.json") != plan["protocol_sha256"] or
            sha256(folder / "evaluation_plan.json") != manifest["evaluation_plan_sha256"]):
        raise ValueError("Changed frozen protocol or evaluation plan")
    for name, digest in plan["source_sha256"].items():
        if sha256(root / "src/carbonroute" / name) != digest:
            raise ValueError(f"Scientific source changed: {name}")
    networks = {}
    for name, evidence in plan["networks"].items():
        data, _, models = reference(root, name)
        networks[name] = data.network
        traffic = root / ("inputs/raw/geant-traffic.tgz" if name == "geant" else "inputs/raw/AbileneTM-all.tar")
        carbon = root / ("inputs/raw/carbon.csv" if name == "geant" else "inputs/raw/eGRID2004_aggregation.xls")
        if (sha256(traffic) != evidence["source"]["traffic_sha256"] or
                sha256(carbon) != evidence["carbon_sha256"] or data.network.graph_hash != evidence["graph_hash"]):
            raise ValueError("Source, carbon or topology changed")
        for filename, digest in evidence["predictor_sha256"].items():
            if sha256(models / filename) != digest:
                raise ValueError("Checkpoint changed")
        if name == "geant" and evidence["source"]["empty_native_sections"]:
            raise ValueError("Native source availability rule violated")
    frame = pd.read_csv(folder / "summary.csv")
    groups = frame.groupby(["network", "window", "scenario"])
    if len(groups) != 2 * protocol["test_days"] * len(protocol["workloads"]):
        raise ValueError("Missing a paired day/workload case")
    for _, group in groups:
        if set(group.policy) != set(protocol["policies"]) or len(group) != len(protocol["policies"]):
            raise ValueError("Missing or duplicate policy")
    for entry in manifest["runs"]:
        run = load_json(folder / entry["file"])
        row, records = run["summary"], run["records"]
        graph = networks[row["network"]]
        offered, served = np.zeros(len(records[0]["routes"])), np.zeros(len(records[0]["routes"]))
        weighted_delay = 0.0
        for record in records:
            routes = [tuple(route) for route in record["routes"]]
            incidence = graph.incidence(routes)
            demand = np.array(record["offered_mbps"])
            actual = np.array(record["served_mbps"])
            if not np.allclose(actual, progressive_fill(demand, incidence, graph.capacities), atol=1e-8):
                raise ValueError("Realized service differs from common max-min allocator")
            if np.any(incidence @ actual > graph.capacities + 1e-7):
                raise ValueError("Realized service exceeds capacity")
            offered += demand
            served += actual
            weighted_delay += sum(actual[i] * graph.delay(route) for i, route in enumerate(routes))
        fractions = np.divide(served, offered, out=np.ones_like(served), where=offered > 0)
        if (offered > 0).any() and not np.isclose(row["min_pair_service_fraction"], fractions[offered > 0].min()):
            raise ValueError("Incorrect per-pair service")
        if served.sum() > 0 and not np.isclose(row["mean_served_path_delay_ms"], weighted_delay / served.sum()):
            raise ValueError("Incorrect modeled path delay")
    if sha256(folder / "day_cluster_intervals.csv") != manifest["day_cluster_intervals_sha256"]:
        raise ValueError("Changed uncertainty output")
    print("Service-first lineage, all paired policies, per-pair service, common allocation and path delay verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    audit(args.root.resolve(), args.folder.resolve())
