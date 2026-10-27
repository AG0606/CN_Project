"""Post-evaluation source-availability audit; never filters or changes the experiment."""
import argparse
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd

from carbonroute.common import load_json, save_json, sha256
from carbonroute.data import parse_demand
from carbonroute.followup_data import load
from carbonroute.network import section


def audit(root: Path, folder: Path) -> None:
    plan = load_json(folder / "evaluation_plan.json")
    archive_path = root / "inputs/raw/geant-traffic.tgz"
    expected = next(value for key, value in plan["networks"]["geant"]["sources"].items()
                    if key.replace("\\", "/").endswith("geant-traffic.tgz"))
    if sha256(archive_path) != expected:
        raise ValueError("Source differs from evaluated archive")
    data = load(root, "geant")
    lo, hi = data.manifest["splits"]["test"]
    first, last = data.times[lo], data.times[hi-1]
    records = []
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".txt"):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Missing source member")
            text = stream.read().decode("utf-8")
            stamp, matrix, _ = parse_demand(text)
            if first <= stamp <= last:
                k = int(np.searchsorted(data.times, stamp))
                records.append({"traffic_day": str(stamp)[:10],
                                "empty_demand_sections": int(not section(text, "DEMANDS")),
                                "zero_retained_matrices": int(matrix.sum() == 0),
                                "zero_selected_matrices": int(data.rates[k].sum() == 0),
                                "source_matrices": 1})
    frame = pd.DataFrame(records).groupby("traffic_day", as_index=False).sum()
    path = folder / "source_availability.csv"
    frame.to_csv(path, index=False)
    summary = pd.read_csv(folder / "summary.csv")
    empty = summary[summary.offered_mb == 0]
    result = {
        "purpose": "Post-evaluation audit of native source availability; no input, model, period or outcome changed",
        "source_sha256": expected,
        "source_availability_sha256": sha256(path),
        "zero_offered_policy_runs": len(empty),
        "zero_offered_days": {name: sorted(group.traffic_day.unique().tolist())
                              for name, group in empty.groupby("network")},
        "interpretation": "An empty native DEMANDS section establishes no listed demands, not measured zero real-world traffic or a known outage. The fixed parser treats unlisted demands as zero. Keep all declared days and mark carbon scores undefined when no bytes are served.",
        "interval_warning": "The frozen day_cluster_intervals.csv has undefined GÉANT carbon-score differences and intervals because empty-day NaNs propagated. Its count of seven includes empty days; only four routing days have defined carbon scores. No carbon-score confidence claim is supported by those GÉANT rows.",
    }
    save_json(folder / "data_quality_audit.json", result)
    print(frame.to_string(index=False))
    print(f"Zero-offered policy runs: {len(empty)}; source audit saved without changing evaluated evidence.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    audit(args.root.resolve(), args.folder.resolve())
