"""Collect the exact local input files into a professor-friendly datasets folder.

Raw files use hard links on the same drive, so the presentation folder does not
consume another several hundred megabytes. Copying or zipping datasets/ still
includes the complete file bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from carbonroute.abilene import CITY, IDS, REGION, egrid_rates

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "datasets"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def place(source: Path, relative: str, expected_sha256: str | None = None) -> dict:
    source = source.resolve(strict=True)
    if not source.is_relative_to(ROOT.resolve()):
        raise ValueError(f"Dataset source escaped the project: {source}")
    target = (DEST / relative).resolve()
    if not target.is_relative_to(DEST.resolve()):
        raise ValueError(f"Dataset destination escaped datasets/: {target}")
    checksum = digest(source)
    if expected_sha256 is not None and checksum != expected_sha256:
        raise ValueError(f"Source checksum mismatch: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if digest(target) != checksum:
            raise ValueError(f"Existing dataset copy differs: {target}")
        method = "existing verified"
    else:
        try:
            os.link(source, target)
            method = "hard link"
        except OSError:
            temporary = target.with_name(target.name + ".partial")
            shutil.copy2(source, temporary)
            if digest(temporary) != checksum:
                raise ValueError(f"Copy checksum mismatch: {temporary}")
            temporary.replace(target)
            method = "copy"
    return {"path": relative.replace("\\", "/"),
            "source_cache": source.relative_to(ROOT).as_posix(),
            "bytes": source.stat().st_size, "sha256": checksum, "local_method": method}


def traffic_preview(source: Path, manifest: dict, bins: int, destination: Path) -> None:
    with np.load(source, allow_pickle=False) as data:
        all_times = data["times"]
        first = next((i for i in range(len(all_times) - bins + 1)
                      if all_times[i] == all_times[i].astype("datetime64[D]") and
                      np.all(np.diff(all_times[i:i + bins]) ==
                             np.timedelta64(24 * 60 // bins, "m"))), None)
        if first is None:
            raise ValueError(f"No complete first calendar day in {source}")
        times = all_times[first:first + bins]
        raw = data["full_mbps"][first:first + bins]
    labels = manifest["graph"]["node_ids"]
    columns = {"source_timestamp": [str(t) for t in times]}
    for a, b in manifest["pairs"]:
        columns[f"{labels[a]}__to__{labels[b]}_Mbps"] = raw[:, a, b].round(6)
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns).to_csv(destination, index=False)


def main() -> None:
    raw = ROOT / "inputs/raw"
    prepared = ROOT / "inputs/processed"
    geant_sources = json.loads((raw / "sources.json").read_text(encoding="utf-8"))
    abilene_sources = json.loads((raw / "abilene-sources.json").read_text(encoding="utf-8"))
    geant_manifest = json.loads((prepared / "manifest.json").read_text(encoding="utf-8"))
    abilene_manifest = json.loads((prepared / "abilene/manifest.json").read_text(encoding="utf-8"))
    entries: list[dict] = []

    def add(source: Path, relative: str, info: dict | None = None) -> None:
        row = place(source, relative, info.get("sha256") if info else None)
        if info and "url" in info:
            row["source_url"] = info["url"]
        entries.append(row)

    for filename in ("geant.txt", "geant-traffic.tgz"):
        add(raw / filename, f"originals/geant/{filename}", geant_sources[filename])
    add(raw / "carbon.csv", "originals/european-carbon/ECON-PowerCI_2015_2024.csv",
        geant_sources["carbon.csv"])
    for filename in ("Abilene-A.txt", "Abilene-readme.txt", "Abilene.graphml"):
        add(raw / filename, f"originals/abilene/{filename}", abilene_sources[filename])
    for week in range(1, 5):
        filename = f"X{week:02}.gz"
        add(raw / "abilene" / filename, f"originals/abilene/{filename}",
            abilene_sources[filename])
    add(raw / "AbileneTM-all.tar", "originals/abilene/AbileneTM-all.tar",
        {"url": "https://www.cs.utexas.edu/~yzhang/research/AbileneTM/AbileneTM-all.tar"})
    for filename in ("egrid_historical_files_1996-2016.zip", "eGRID2004_aggregation.xls"):
        add(raw / filename, f"originals/epa/{filename}", abilene_sources[filename])
    add(raw / "eGRID2004_TechnicalSupportDocument.pdf",
        "originals/epa/eGRID2004_TechnicalSupportDocument.pdf")
    for study, folder, manifest in (("geant", prepared, geant_manifest),
                                    ("abilene", prepared / "abilene", abilene_manifest)):
        add(folder / "traffic.npz", f"processed/{study}/traffic.npz",
            {"sha256": manifest["traffic_sha256"]})
        add(folder / "manifest.json", f"processed/{study}/manifest.json")

    previews = DEST / "previews"
    traffic_preview(prepared / "traffic.npz", geant_manifest, 96,
                    previews / "geant_traffic_first_day_selected_OD.csv")
    traffic_preview(prepared / "abilene/traffic.npz", abilene_manifest, 288,
                    previews / "abilene_traffic_first_day_selected_OD.csv")
    carbon = pd.read_csv(raw / "carbon.csv")
    countries = {"FRA", "DEU", "BEL", "NLD", "CHE", "ITA", "AUT", "LUX"}
    dates = pd.to_datetime(carbon.Timestamp, format="%Y/%m/%d")
    sample = carbon[carbon.ISO.isin(countries) &
                    dates.between("2022-06-06", "2022-06-12")].copy()
    sample.to_csv(previews / "european_carbon_2022_sample.csv", index=False)
    pounds, grams = egrid_rates(raw / "eGRID2004_aggregation.xls")
    pd.DataFrame([{"router": router, "city": city, "eGRID_subregion": region,
                   "annual_CO2_lb_per_MWh": pounds[region],
                   "annual_CO2_g_per_kWh": grams[region]}
                  for router, city, region in zip(IDS, CITY, REGION)]).to_csv(
                      previews / "epa2004_router_region_rates.csv", index=False)
    for path in sorted(previews.glob("*.csv")):
        entries.append({"path": path.relative_to(DEST).as_posix(), "bytes": path.stat().st_size,
                        "sha256": digest(path), "kind": "readable preview, not a separate source"})

    (DEST / "MANIFEST.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Local presentation index. Original files remain in inputs/raw for the code.",
        "files": entries,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Dataset folder ready: {DEST}")
    print(f"{len(entries)} verified files; originals are local and are excluded from Git")


if __name__ == "__main__":
    main()
