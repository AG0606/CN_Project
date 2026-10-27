"""One self-contained, two-tab viewer for the GÉANT and Abilene campaigns."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .common import load_json, sha256

LABELS = {
    "shortest_path": "Shortest path",
    "reactive_carbon": "Reactive carbon",
    "predictive_te": "Predictive TE",
    "predictive_carbon": "GNN + safeguards",
    "persistence_carbon": "Persistence + safeguards",
    "no_margin": "GNN without margin",
    "no_hysteresis": "GNN without hysteresis",
}


def _campaign(folder: Path, kind: str) -> dict[str, Any]:
    manifest = load_json(folder / "manifest.json")
    if manifest.get("status") != "complete":
        raise ValueError(f"{kind} campaign is incomplete")
    if sha256(folder / "summary.csv") != manifest["summary_sha256"]:
        raise ValueError(f"{kind} summary checksum mismatch")
    for name in ("forecast_metrics.csv", "training_summary.json"):
        if sha256(folder / name) != manifest[name.split(".")[0] + "_sha256"]:
            raise ValueError(f"{kind} evidence checksum mismatch: {name}")
    frame = pd.read_csv(folder / "summary.csv")
    first_year = int(frame.carbon_year.min())
    selected = frame[(frame.window == 0) & (frame.carbon_year == first_year)]
    entries = {entry["run_id"]: entry for entry in manifest["runs"]}
    runs = {}
    for row in selected.itertuples():
        entry = entries[row.run_id]
        path = (folder / entry["file"]).resolve()
        if not path.is_relative_to((folder / "runs").resolve()) or sha256(path) != entry["sha256"]:
            raise ValueError(f"{kind} run checksum/path mismatch: {row.run_id}")
        runs[row.run_id] = load_json(path)
    return {
        "manifest": manifest,
        "summary": json.loads(frame.to_json(orient="records")),
        "forecast": json.loads(pd.read_csv(folder / "forecast_metrics.csv").to_json(orient="records")),
        "training": load_json(folder / "training_summary.json"),
        "runs": runs,
    }


def build_dashboard(root: Path, abilene_folder: Path | None = None) -> Path:
    """Regenerate the single offline HTML from both completed result folders."""
    geant = _campaign(root / "results/demo", "GÉANT")
    abilene = _campaign(abilene_folder or root / "results/abilene", "Abilene")
    geant["alignments"] = {
        str(year): load_json(root / "results/demo" / f"alignment_{year}.json")
        for year in sorted({row["carbon_year"] for row in geant["summary"]})
    }
    payload = {"geant": geant, "abilene": abilene, "labels": LABELS}
    pilot = root / "results/tradeoff-study-20261027-v2"
    if (pilot / "manifest.json").exists():
        pilot_manifest = load_json(pilot / "manifest.json")
        if (pilot_manifest.get("status") != "complete" or
                sha256(pilot / "summary.csv") != pilot_manifest["summary_sha256"]):
            raise ValueError("Exploratory tradeoff evidence is incomplete or has changed")
        payload["tradeoff"] = {
            "summary": json.loads(pd.read_csv(pilot / "summary.csv").to_json(orient="records")),
            "days": {name: info["days"] for name, info in pilot_manifest["networks"].items()},
        }
    service_first = root / "results/service-first-20261027"
    if (service_first / "manifest.json").exists():
        study = load_json(service_first / "manifest.json")
        if study.get("status") == "complete":
            if (sha256(service_first / "summary.csv") != study["summary_sha256"] or
                    sha256(service_first / "evaluation_plan.json") != study["evaluation_plan_sha256"]):
                raise ValueError("Service-first study evidence changed")
            payload["service_first"] = {
                "summary": json.loads(pd.read_csv(service_first / "summary.csv").to_json(orient="records")),
                "days": {name: info["days"] for name, info in study["networks"].items()},
            }
    multipath = root / "results/multipath-20261027-v2"
    if (multipath / "manifest.json").exists():
        study = load_json(multipath / "manifest.json")
        if study.get("status") == "complete":
            if (sha256(multipath / "summary.csv") != study["summary_sha256"] or
                    sha256(multipath / "evaluation_plan.json") != study["evaluation_plan_sha256"]):
                raise ValueError("Multipath evidence changed")
            frame = pd.read_csv(multipath / "summary.csv")
            examples = {}
            for (name, scenario), group in frame[frame.policy == "multipath_carbon_gnn"].groupby(["network", "scenario"]):
                # First chronological material split, never an outcome-selected best case.
                found = False
                for row in group.sort_values("window").itertuples():
                    run_id = f"{name}_d{row.window}_{scenario}_multipath_carbon_gnn"
                    entry = next(item for item in study["runs"] if item["run_id"] == run_id)
                    path = (multipath / entry["file"]).resolve()
                    if not path.is_relative_to((multipath / "runs").resolve()) or sha256(path) != entry["sha256"]:
                        raise ValueError("Changed multipath example log")
                    run = load_json(path)
                    owners = run["path_owners"]
                    for record in run["records"]:
                        for f in sorted(set(owners)):
                            indices = [i for i, owner in enumerate(owners)
                                       if owner == f and record["path_fractions"][i] >= .01]
                            if len(indices) < 2:
                                continue
                            examples[f"{name}_{scenario}"] = {
                                "traffic_time": record["traffic_time"], "pair_index": f,
                                "paths": [{"nodes": run["candidate_routes"][i], "fraction": record["path_fractions"][i]}
                                          for i, owner in enumerate(owners) if owner == f and record["path_fractions"][i] > 1e-6],
                                "offered_mbps": record["offered_mbps"][f], "served_mbps": record["served_mbps"][f]}
                            found = True
                            break
                        if found:
                            break
                    if found:
                        break
            payload["multipath"] = {"summary": json.loads(frame.to_json(orient="records")), "examples": examples,
                                    "days": {name: info["days"] for name, info in study["networks"].items()}}
    template = Path(__file__).with_name("combined_dashboard.html").read_text(encoding="utf-8")
    embedded = json.dumps(payload, separators=(", ", ":"), allow_nan=False).replace("<", "\\u003c")
    path = root / "results/demo/index.html"
    for marker, filename in (
        ("__PANGOLIN_FONT__", "Pangolin-Regular-latin.woff2"),
        ("__POPPINS_REGULAR_FONT__", "Poppins-Regular-latin.woff2"),
        ("__POPPINS_BOLD_FONT__", "Poppins-Bold-latin.woff2"),
    ):
        font_path = root / "assets/fonts" / filename
        template = template.replace(marker, base64.b64encode(font_path.read_bytes()).decode("ascii"))
    path.write_text(template.replace("__DATA__", embedded), encoding="utf-8")
    return path
