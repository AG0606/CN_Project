"""Screen native GÉANT availability chronologically without reading routing outcomes."""
import argparse
import tarfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from carbonroute.common import load_json, save_json, sha256
from carbonroute.network import section


def screen(root: Path, output: Path, first_day: str, days: int) -> None:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Choose a new empty availability-screen folder")
    archive_path = root / "inputs/raw/geant-traffic.tgz"
    expected = load_json(root / "inputs/processed/manifest.json")["sources"]["geant-traffic.tgz"]["sha256"]
    if sha256(archive_path) != expected:
        raise ValueError("Changed GÉANT source")
    available = {}
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".txt"):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Missing native member")
            text = stream.read().decode("utf-8")
            meta = dict(line.split("=", 1) for line in section(text, "META"))
            meta = {key.strip(): value.strip() for key, value in meta.items()}
            stamp = np.datetime64(datetime.strptime(meta["time"], "%Y%m%d-%H%M"), "m")
            available[stamp] = bool(section(text, "DEMANDS"))
    first = np.datetime64(first_day, "m")
    last = max(available)-np.timedelta64(days, "D")
    rows, selected = [], None
    for day in np.arange(first, last+np.timedelta64(1, "D"), np.timedelta64(1, "D")):
        stamps = np.arange(day-np.timedelta64(3, "h"), day+np.timedelta64(days, "D"), np.timedelta64(15, "m"))
        missing = sum(not available.get(stamp, False) for stamp in stamps)
        rows.append({"candidate_start": str(day)[:10], "unavailable_bins_in_seven_days_and_initial_lookback": missing})
        if missing == 0 and selected is None:
            selected = str(day)[:10]
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "SOURCE_AVAILABILITY_SCREEN.csv", index=False)
    save_json(output / "SOURCE_SELECTION.json", {
        "rule": f"First {days}-consecutive-day period starting on/after {first_day} with nonempty native sections and initial 3-hour lookback; availability only, no traffic magnitude/carbon/policy outcomes",
        "selected_start": selected, "source_sha256": expected})
    print(f"Source-only selection: {selected}; all candidate counts retained in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first", default="2005-07-22")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    if args.days < 1:
        parser.error("days must be positive")
    screen(args.root.resolve(), args.output.resolve(), args.first, args.days)
