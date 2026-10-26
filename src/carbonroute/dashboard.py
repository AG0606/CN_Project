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
