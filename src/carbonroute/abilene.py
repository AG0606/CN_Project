"""Same-year US Abilene OD and EPA eGRID2004 secondary experiment.

Traffic is NetFlow-derived; EPA rates are annual regional generation averages.
The carbon-weighted forwarding metric is a routing proxy, not measured CO2.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
import xlrd

from .common import ROOT, config, fingerprint, save_json, sha256
from .data import Prepared, choose_pairs, window_indices
from .experiments import paired_differences, workload
from .network import Network
from .prediction import Persistence, TrainedPredictor, train
from .routing import POLICIES
from .simulation import replay

IDS = ("ATLA-M5", "ATLAng", "CHINng", "DNVRng", "HSTNng", "IPLSng",
       "KSCYng", "LOSAng", "NYCMng", "SNVAng", "STTLng", "WASHng")
CITY = ("Atlanta", "Atlanta", "Chicago", "Denver", "Houston", "Indianapolis",
        "Kansas City", "Los Angeles", "New York", "Sunnyvale", "Seattle", "Washington DC")
REGION = ("SRSO", "SRSO", "RFCW", "RMPA", "ERCT", "RFCW", "SRMW", "CAMX",
          "NYCW", "CAMX", "NWPP", "RFCE")
WEEK_START = ("2004-03-01", "2004-03-08", "2004-04-02", "2004-04-09")
TRACE = "https://www.cs.utexas.edu/~yzhang/research/AbileneTM/"
ZOO = "https://raw.githubusercontent.com/mroughan/InternetTopologyZoo/main/graphml/Abilene.graphml"
EPA = "https://www.epa.gov/system/files/other-files/2023-01/egrid_historical_files_1996-2016.zip"
EPA_MEMBER = "egrid_historical_files_1996-2016/eGRID2004_aggregation.xls"
LB_MWH_TO_G_KWH = 0.45359237
SOURCE_SHA256 = {
    "Abilene-A.txt": "228e49b6ce34457f283aca179174fae2443573a2a3672d0413383c58aed989d3",
    "Abilene-readme.txt": "caa200883f4f29938c063ea01a188f01494ed1d1a43c854a375a3e11bfe473c9",
    "Abilene.graphml": "8cd694280d98b336bb9b51fc3b2129a514f1b1b1ac80f2022aca02a57ef1e371",
    "egrid_historical_files_1996-2016.zip": "14503dcdf10c3d61a819a82be358e1c118991a6cf7f1901be291990104b74857",
    "X01.gz": "d996a9115d2815eec158d5055452deb389f5546a96e0dfcbfae5c22a40372558",
    "X02.gz": "e4646c3020e5904b3e4f3388899c15940b8156ade9fdaf9dd96b06a83f8066a5",
    "X03.gz": "b90f058def353a78db4e5d65d329de867659add90b7ef4d918acb7ba88a8f040",
    "X04.gz": "3aab7fe56b84f2469888a142c2af313c865d4c3d41c955cdc199ccea4c66cce0",
    "eGRID2004_aggregation.xls": "48c3a413a1f5eb54e1604713efd1d523fd0dc94a23fb2582f9c0cb86d51a7104",
}


def _fetch(path: Path, url: str, max_bytes: int) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Abilene-EPA-research/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as out:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Source exceeded size limit: {url}")
            out.write(chunk)
    part.replace(path)


def sources(root: Path, weeks: int) -> dict[str, Any]:
    if weeks != 4:
        raise ValueError("This preregistered secondary experiment uses X01–X04")
    raw = root / "inputs/raw"
    items = {"Abilene-A.txt": (TRACE + "A", 100_000),
             "Abilene-readme.txt": (TRACE + "readme.txt", 100_000),
             "Abilene.graphml": (ZOO, 100_000),
             "egrid_historical_files_1996-2016.zip": (EPA, 200_000_000)}
    for name, (url, limit) in items.items():
        _fetch(raw / name, url, limit)
    for i in range(1, weeks + 1):
        name = f"X{i:02}.gz"
        _fetch(raw / "abilene" / name, TRACE + name, 20_000_000)
    with zipfile.ZipFile(raw / "egrid_historical_files_1996-2016.zip") as archive:
        if EPA_MEMBER not in archive.namelist():
            raise ValueError("EPA historical archive lacks eGRID2004 aggregation workbook")
        target = raw / "eGRID2004_aggregation.xls"
        if not target.exists():
            target.write_bytes(archive.read(EPA_MEMBER))
    paths = [raw / name for name in items]
    paths += [raw / "abilene" / f"X{i:02}.gz" for i in range(1, weeks + 1)]
    paths += [raw / "eGRID2004_aggregation.xls"]
    records = {}
    for path in paths:
        digest = sha256(path)
        if digest != SOURCE_SHA256[path.name]:
            raise ValueError(f"Source checksum mismatch: {path}. Remove it and retry")
        records[path.name] = {
            "url": (items[path.name][0] if path.name in items else
                    TRACE + path.name if path.suffix == ".gz" else EPA + "#" + EPA_MEMBER),
            "bytes": path.stat().st_size, "sha256": digest,
        }
    save_json(raw / "abilene-sources.json", records)
    return records


def topology(a_text: str, zoo_path: Path, cfg: dict[str, Any]) -> Network:
    directed = set()
    for line in a_text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        link = line.split()[0].split(",")
        if len(link) == 2 and "*" not in link:
            if set(link) - set(IDS):
                raise ValueError("Unknown 2004 Abilene router in routing matrix")
            directed.add(tuple(link))
    edges = sorted({(min(IDS.index(a), IDS.index(b)), max(IDS.index(a), IDS.index(b)))
                    for a, b in directed})
    if len(edges) != 15 or len(directed) != 30:
        raise ValueError("Expected 15 bidirectional 2004 Abilene links")
    graph = nx.read_graphml(zoo_path)
    by_city = {attributes["label"]: attributes for _, attributes in graph.nodes(data=True)}
    if set(CITY) != set(by_city):
        raise ValueError("Topology Zoo coordinates do not match trace cities")
    coords = [(float(by_city[city]["Longitude"]), float(by_city[city]["Latitude"]))
              for city in CITY]
    zoo_edges = {frozenset((graph.nodes[a]["label"], graph.nodes[b]["label"]))
                 for a, b in graph.edges()}
    trace_city_edges = {frozenset((CITY[a], CITY[b])) for a, b in edges if CITY[a] != CITY[b]}
    if zoo_edges != trace_city_edges:
        raise ValueError("2004 trace links disagree with the 2005 coordinate snapshot")
    return Network(coords, edges, [f"{IDS[a]},{IDS[b]}" for a, b in edges],
                   cfg["capacity_mbps"], cfg["fiber_stretch"], cfg["router_delay_ms"],
                   IDS, REGION)


def egrid_rates(path: Path) -> tuple[dict[str, float], dict[str, float]]:
    sheet = xlrd.open_workbook(path).sheet_by_name("EGRDSRL04")
    headings = [str(sheet.cell_value(4, col)).strip() for col in range(sheet.ncols)]
    if headings[1] != "SUBRGN" or headings[17] != "SRCO2RTA":
        raise ValueError("Unexpected eGRID2004 region/annual-CO2 columns")
    pounds: dict[str, float] = {}
    for row in range(5, sheet.nrows):
        code = str(sheet.cell_value(row, 1)).strip()
        value = sheet.cell_value(row, 17)
        if code in REGION and isinstance(value, (int, float)):
            if code in pounds:
                raise ValueError(f"Duplicate EPA subregion {code}")
            pounds[code] = float(value)
    if set(pounds) != set(REGION) or any(v <= 0 for v in pounds.values()):
        raise ValueError("Missing or invalid EPA eGRID2004 annual CO2 rates")
    return pounds, {region: rate * LB_MWH_TO_G_KWH for region, rate in pounds.items()}


def read_week(path: Path, first_day: str) -> tuple[np.ndarray, np.ndarray]:
    times = np.datetime64(first_day, "m") + np.arange(2016) * np.timedelta64(5, "m")
    matrices = np.empty((2016, 12, 12), dtype=np.float32)
    with gzip.open(path, "rt") as stream:
        row_count = 0
        for i, line in enumerate(stream):
            if i >= 2016:
                raise ValueError(f"Unexpected extra rows in {path}")
            fields = np.fromstring(line, sep=" ", dtype=np.float64)
            if fields.size != 720 or not np.isfinite(fields).all() or (fields < 0).any():
                raise ValueError(f"Malformed Abilene traffic row {i} in {path}")
            matrices[i] = fields[::5].reshape(12, 12) * (100 * 8 / (300 * 1e6))
            row_count += 1
        if row_count != 2016:
            raise ValueError(f"Expected 2016 five-minute matrices in {path}, got {row_count}")
    return times, matrices


def prepare(root: Path, cfg: dict[str, Any]) -> Prepared:
    records = sources(root, cfg["traffic_weeks"])
    raw = root / "inputs/raw"
    network = topology((raw / "Abilene-A.txt").read_text(), raw / "Abilene.graphml", cfg)
    pounds, grams = egrid_rates(raw / "eGRID2004_aggregation.xls")
    weekly = [read_week(raw / "abilene" / f"X{i:02}.gz", day)
              for i, day in enumerate(WEEK_START, 1)]
    times = np.concatenate([item[0] for item in weekly])
    full = np.concatenate([item[1] for item in weekly])
    splits = {"train": [0, 4032], "validation": [4032, 6048], "test": [6048, 8064]}
    pairs = choose_pairs(full[:4032], network, cfg)
    mask = np.zeros((12, 12), dtype=np.float32)
    for a, b in pairs:
        mask[a, b] = 1
    rates = full * mask
    shortest = [paths[0] for paths in network.candidates(pairs, 1, 1)]
    train_rates = rates[:4032, [a for a, _ in pairs], [b for _, b in pairs]]
    max_load = (train_rates @ network.incidence(shortest).T).max(axis=1)
    factor = cfg["train_utilization_p95"] * cfg["capacity_mbps"] / float(np.quantile(max_load, .95))
    rates *= factor
    scale = np.maximum(np.quantile(rates[:4032], .95, axis=0), .01).astype(np.float32)
    scale[mask == 0] = 1
    counts = {split: len(window_indices(times, bounds[0], bounds[1], cfg["lookback"], cfg["horizon"], 300))
              for split, bounds in splits.items()}
    cache = root / "inputs/processed/abilene"
    cache.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache / "traffic.npz", times=times, full_mbps=full,
                        rates=rates, mask=mask, scale=scale)
    metadata = {"schema_version": 1, "dataset": "Abilene + EPA eGRID2004",
                "config": cfg, "config_hash": fingerprint(cfg), "sources": records,
                "graph": network.metadata(), "graph_hash": network.graph_hash,
                "splits": splits, "window_counts": counts, "pairs": pairs,
                "pair_ids": [[IDS[a], IDS[b]] for a, b in pairs],
                "weeks": [{"file": f"X{i:02}.gz", "first_day": day} for i, day in enumerate(WEEK_START, 1)],
                "traffic_unit_conversion": "realOD * 100 bytes * 8 bits / 300 s / 1e6 = Mbps",
                "traffic_factor": factor, "capacity_note": "10 Mbps is an experiment assumption, not a measured Abilene link capacity",
                "carbon_regions": dict(zip(IDS, REGION)), "epa_annual_lb_per_mwh": pounds,
                "epa_annual_g_per_kwh": grams,
                "carbon_note": "EPA 2004 annual generation output rates; spatial differences only, fixed within replay; approximate city-to-subregion mapping",
                "score_note": "Carbon-weighted forwarding attribution, not physical energy or measured CO2",
                "traffic_sha256": sha256(cache / "traffic.npz")}
    save_json(cache / "manifest.json", metadata)
    return Prepared(times, rates, mask, scale, network, pairs, metadata)


def load_prepared(root: Path, cfg: dict[str, Any]) -> Prepared:
    folder = root / "inputs/processed/abilene"
    meta = json.loads((folder / "manifest.json").read_text())
    if meta["config_hash"] != fingerprint(cfg) or sha256(folder / "traffic.npz") != meta["traffic_sha256"]:
        raise ValueError("Abilene prepared data/config mismatch; rerun prepare")
    raw = root / "inputs/raw"
    network = topology((raw / "Abilene-A.txt").read_text(), raw / "Abilene.graphml", cfg)
    if network.graph_hash != meta["graph_hash"]:
        raise ValueError("Abilene graph changed after preparation")
    with np.load(folder / "traffic.npz", allow_pickle=False) as z:
        return Prepared(z["times"], z["rates"], z["mask"], z["scale"], network,
                        [tuple(pair) for pair in meta["pairs"]], meta)


def test_days(data: Prepared, cfg: dict[str, Any]) -> list[tuple[int, int]]:
    lo, hi = data.manifest["splits"]["test"]
    starts = [k for k in range(lo + cfg["lookback"], hi - 288 + 1)
              if data.times[k] == data.times[k].astype("datetime64[D]") and
              np.all(np.diff(data.times[k-cfg["lookback"]:k+288]) == np.timedelta64(5, "m"))]
    if len(starts) < 2:
        raise ValueError("Need two complete, held-out Abilene test days")
    return [(start, start+288) for start in starts[:2]]


def campaign(root: Path, cfg: dict[str, Any], output: Path, overwrite: bool = False) -> Path:
    if (output / "manifest.json").exists() and not overwrite:
        raise FileExistsError(f"Existing result at {output}; pass --overwrite")
    data = load_prepared(root, cfg)
    folder = root / "artifacts/abilene"
    gnn = TrainedPredictor(folder, data, cfg)
    persistence_info = json.loads((folder / "persistence.json").read_text())
    if persistence_info["config_hash"] != fingerprint(cfg):
        raise ValueError("Persistence model/config mismatch")
    persistence = Persistence(cfg["horizon"], data.mask,
                              np.array(persistence_info["margin_mbps"]))
    rates_by_node = np.array([data.manifest["epa_annual_g_per_kwh"][code] for code in REGION])
    output.mkdir(parents=True, exist_ok=True)
    (output / "runs").mkdir(exist_ok=True)
    for name in ("forecast_metrics.csv", "training_summary.json"):
        shutil.copyfile(folder / name, output / name)
    manifest = {"schema_version": 2, "dataset": "abilene-egrid2004", "status": "running",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "config": cfg, "config_hash": fingerprint(cfg),
                "traffic_manifest": data.manifest, "graph": data.network.metadata(),
                "graph_hash": data.network.graph_hash, "carbon_year": 2004,
                "carbon_sha256": data.manifest["sources"]["eGRID2004_aggregation.xls"]["sha256"],
                "checkpoint_sha256": sha256(folder / "gnn.pt"),
                "forecast_metrics_sha256": sha256(output / "forecast_metrics.csv"),
                "training_summary_sha256": sha256(output / "training_summary.json"),
                "interpretation": data.manifest["carbon_note"] + "; " + data.manifest["score_note"],
                "runs": [], "failed_runs": []}
    rows = []
    for day, (start, stop) in enumerate(test_days(data, cfg)):
        for scenario in ("normal", "congested", "bursty"):
            seed = cfg["seed"] + day * 101
            rates = workload(data, cfg, start, stop, scenario, seed)
            traffic_hash = hashlib.sha256(rates[start-cfg["lookback"]:stop].tobytes()).hexdigest()
            carbon = np.repeat(rates_by_node[None], stop-start, axis=0)
            for policy in POLICIES:
                run_id = f"w{day}_2004_{scenario}_lag1_{policy}"
                predictor = persistence if policy == "persistence_carbon" else gnn
                result = replay(data, cfg, rates, carbon, start, stop, policy, predictor, 1)
                summary = {"run_id": run_id, "window": day, "scenario": scenario,
                           "carbon_year": 2004, "seed": seed, "start": start, "stop": stop,
                           "traffic_start": str(data.times[start]), "traffic_sha256": traffic_hash,
                           **result.summary}
                path = output / "runs" / f"{run_id}.json"
                save_json(path, {"summary": summary, "records": result.records})
                rows.append(summary)
                manifest["runs"].append({"run_id": run_id, "window": day, "scenario": scenario,
                                         "carbon_year": 2004, "policy": policy,
                                         "observation_delay_bins": 1,
                                         "file": f"runs/{run_id}.json", "sha256": sha256(path),
                                         "traffic_sha256": traffic_hash})
            print(f"Completed Abilene test day {day+1}/2, {scenario}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "summary.csv", index=False)
    paired_differences(frame, cfg["seed"]).to_csv(output / "paired_differences.csv", index=False)
    manifest["summary_sha256"] = sha256(output / "summary.csv")
    manifest["status"] = "complete"
    save_json(output / "manifest.json", manifest)
    return output


def report(root: Path, output: Path) -> Path:
    from .dashboard import build_dashboard

    return build_dashboard(root, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Abilene + EPA eGRID2004 secondary experiment")
    parser.add_argument("command", choices=("prepare", "train", "run", "report", "all"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    cfg = config(root / "configs/abilene.json")
    output = (args.output or root / "results/abilene").resolve()
    if args.command in ("prepare", "all"):
        prepare(root, cfg)
        print("Prepared Abilene/EPA data", flush=True)
    if args.command in ("train", "all"):
        train(root, cfg, load_prepared(root, cfg), root / "artifacts/abilene")
    if args.command in ("run", "all"):
        campaign(root, cfg, output, args.overwrite)
    if args.command in ("report", "all"):
        print(report(root, output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
