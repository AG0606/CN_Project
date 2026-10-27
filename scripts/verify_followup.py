"""Audit final follow-up logs, frozen protocol, data splits and checkpoint lineage."""
import argparse
from pathlib import Path

import pandas as pd
from verify_tradeoff import verify

from carbonroute.common import fingerprint, load_json, sha256


def audit(folder: Path, root: Path) -> None:
    verify(folder)
    manifest = load_json(folder / "manifest.json")
    plan = load_json(folder / "evaluation_plan.json")
    protocol = load_json(folder / "protocol.json")
    if sha256(folder / "protocol.json") != plan["protocol_sha256"]:
        raise ValueError("Protocol no longer matches the frozen plan")
    if sha256(folder / "evaluation_plan.json") != manifest["evaluation_plan_sha256"]:
        raise ValueError("Changed evaluation plan")
    for filename, expected in plan["source_sha256"].items():
        if sha256(root / "src/carbonroute" / filename) != expected:
            raise ValueError(f"Scientific source changed since this evaluation: {filename}")
    for name, evidence in plan["networks"].items():
        prepared = root / "inputs/processed/followup" / name
        meta = load_json(prepared / "manifest.json")
        if (sha256(prepared / "traffic.npz") != evidence["traffic_sha256"]
                or meta["protocol_hash"] != fingerprint(protocol)):
            raise ValueError("Changed prepared traffic or split protocol")
        if not (meta["split_dates"]["train"][1] < meta["split_dates"]["validation"][0]
                and meta["split_dates"]["validation"][1] < meta["split_dates"]["test"][0]):
            raise ValueError("Chronological training, validation and test overlap")
        for source, expected in evidence["sources"].items():
            if sha256(root / source.replace("\\", "/")) != expected:
                raise ValueError("Changed original traffic source")
        if sha256(root / evidence["carbon_file"]) != evidence["carbon_sha256"]:
            raise ValueError("Changed carbon source")
        original = root / ("artifacts" if name == "geant" else "artifacts/abilene")
        for kind in ("gnn", "gru"):
            recorded = evidence["predictors"][f"reference_{kind}"]
            if (sha256(original / f"{kind}.pt") != recorded["checkpoint_sha256"]
                    or sha256(original / f"{kind}.json") != recorded["metadata_sha256"]):
                raise ValueError("Original reference checkpoint changed")
        for label, directory in (("reference_persistence", original),
                                  ("updated_persistence", root / "artifacts/followup" / name / "expanded")):
            if sha256(directory / "persistence.json") != evidence["predictors"][label]["metadata_sha256"]:
                raise ValueError("Persistence calibration changed")
        for variant in protocol["training_variants"]:
            directory = root / "artifacts/followup" / name / variant
            training = load_json(directory / "training_summary.json")
            if training.get("test_evaluated") is not False:
                raise ValueError("Final test used by a training routine")
            forecast = pd.read_csv(directory / "forecast_metrics.csv")
            if set(forecast.split) != {"validation"}:
                raise ValueError("Training artifacts include a final-test evaluation")
            for kind in ("gnn", "gru"):
                model = evidence["predictors"][f"{variant}_{kind}"]
                if (sha256(directory / f"{kind}.pt") != model["checkpoint_sha256"]
                        or sha256(directory / f"{kind}.json") != model["metadata_sha256"]):
                    raise ValueError("Checkpoint changed after final evaluation freeze")
    frame = pd.read_csv(folder / "summary.csv")
    sizes = frame.groupby(["network", "window", "scenario"]).size()
    if len(sizes) != 2 * protocol["test_days_per_network"] * len(protocol["scenarios"]) or not (sizes == 15).all():
        raise ValueError("Missing declared policy or paired case")
    for filename in ("forecast_metrics.csv", "day_cluster_intervals.csv"):
        if sha256(folder / filename) != manifest[filename.removesuffix(".csv") + "_sha256"]:
            raise ValueError("Changed result evidence")
    quality_path = folder / "data_quality_audit.json"
    if quality_path.exists():
        quality = load_json(quality_path)
        if sha256(folder / "source_availability.csv") != quality["source_availability_sha256"]:
            raise ValueError("Changed post-evaluation source-availability evidence")
        empty = frame[frame.offered_mb == 0]
        days = {name: sorted(group.traffic_day.unique().tolist())
                for name, group in empty.groupby("network")}
        if len(empty) != quality["zero_offered_policy_runs"] or days != quality["zero_offered_days"]:
            raise ValueError("Source-quality disclosure differs from saved runs")
    print("Follow-up lineage verified: frozen protocol and sources, disjoint chronological splits, "
          "training without final-test evaluation, and all declared paired cases.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    audit(args.folder.resolve(), args.root.resolve())
