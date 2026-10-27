"""Later chronological windows with the reference training-only transforms frozen."""
from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import numpy as np

from . import abilene
from .common import config, fingerprint, load_json, save_json, sha256
from .data import Prepared, load_prepared, read_archive, window_indices


def reference(root: Path, name: str) -> tuple[Prepared, dict, Path]:
    cfg = config(root / ("configs/default.json" if name == "geant" else "configs/abilene.json"))
    data = load_prepared(root, cfg) if name == "geant" else abilene.load_prepared(root, cfg)
    folder = root / ("artifacts" if name == "geant" else "artifacts/abilene")
    return data, cfg, folder


def prepare(root: Path, name: str, protocol: dict) -> Prepared:
    original, cfg, _ = reference(root, name)
    if name == "geant":
        path = root / "inputs/raw/geant-traffic.tgz"
        expected = original.manifest["sources"][path.name]["sha256"]
        if sha256(path) != expected:
            raise ValueError("Changed GÉANT archive")
        times, full, _ = read_archive(path)
        dates = protocol["geant"]
        keep = times < np.datetime64(dates["test_end_exclusive"])
        times, full = times[keep], full[keep]
        a = int(np.searchsorted(times, np.datetime64(dates["training_end_exclusive"])))
        b = int(np.searchsorted(times, np.datetime64(dates["validation_end_exclusive"])))
        splits = {"train": [0, a], "validation": [a, b], "test": [b, len(times)]}
        sources = {str(path.relative_to(root)): expected}
    else:
        info = protocol["abilene"]
        archive_path = root / "inputs/raw/AbileneTM-all.tar"
        if sha256(archive_path) != info["archive_sha256"]:
            raise ValueError("Changed Abilene archive")
        weekly, sources = [], {str(archive_path.relative_to(root)): info["archive_sha256"]}
        weeks = info["training_weeks"] + info["validation_weeks"] + info["test_weeks"]
        if weeks != list(range(1, len(weeks)+1)):
            raise ValueError("Expected ordered source weeks without duplicate memberships")
        with tarfile.open(archive_path) as archive:
            for number in weeks:
                filename = f"X{number:02d}.gz"
                member = archive.getmember(filename)
                if not member.isfile() or member.size > 20_000_000:
                    raise ValueError("Unexpected Abilene archive member")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Missing Abilene member")
                content = stream.read()
                expected = hashlib.sha256(content).hexdigest()
                target = root / "inputs/raw/abilene" / filename
                if target.exists() and sha256(target) != expected:
                    raise ValueError(f"Cached week disagrees with verified archive: {filename}")
                if not target.exists():
                    target.write_bytes(content)
                sources[str(target.relative_to(root))] = expected
                weekly.append(abilene.read_week(target, info["week_starts"][number-1]))
        times = np.concatenate([x[0] for x in weekly])
        full = np.concatenate([x[1] for x in weekly])
        a = len(info["training_weeks"]) * 2016
        b = a + len(info["validation_weeks"]) * 2016
        splits = {"train": [0, a], "validation": [a, b], "test": [b, len(times)]}
    # Identical original pair set, rate factor and normalizer for every predictor.
    rates = full * original.mask * original.manifest["traffic_factor"]
    counts = {s: len(window_indices(times, bounds[0], bounds[1], cfg["lookback"], cfg["horizon"], cfg["bin_seconds"]))
              for s, bounds in splits.items()}
    if min(counts.values()) == 0:
        raise ValueError("Empty contiguous training/validation/test windows")
    folder = root / "inputs/processed/followup" / name
    folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(folder / "traffic.npz", times=times, rates=rates,
                        mask=original.mask, scale=original.scale)
    meta = {"network": name, "protocol_hash": fingerprint(protocol), "splits": splits, "window_counts": counts,
            "sources": sources, "reference_traffic_sha256": original.manifest["traffic_sha256"],
            "traffic_sha256": sha256(folder / "traffic.npz"), "graph": original.network.metadata(),
            "graph_hash": original.network.graph_hash, "pairs": original.manifest["pairs"],
            "traffic_factor": original.manifest["traffic_factor"],
            "normalization": "Frozen reference training-only scale and demand selection",
            "split_dates": {s: [str(times[a]), str(times[b-1])] for s, (a, b) in splits.items()}}
    save_json(folder / "manifest.json", meta)
    return Prepared(times, rates, original.mask, original.scale, original.network, original.pairs, meta)


def load(root: Path, name: str) -> Prepared:
    original, _, _ = reference(root, name)
    folder = root / "inputs/processed/followup" / name
    meta = load_json(folder / "manifest.json")
    if (sha256(folder / "traffic.npz") != meta["traffic_sha256"]
            or original.network.graph_hash != meta["graph_hash"]
            or original.manifest["traffic_sha256"] != meta["reference_traffic_sha256"]):
        raise ValueError("Follow-up data or reference transforms changed")
    with np.load(folder / "traffic.npz", allow_pickle=False) as z:
        if not np.array_equal(z["mask"], original.mask) or not np.array_equal(z["scale"], original.scale):
            raise ValueError("Follow-up transforms differ from frozen reference training transforms")
        return Prepared(z["times"], z["rates"], z["mask"], z["scale"], original.network,
                        original.pairs, meta)


def test_days(data: Prepared, cfg: dict, count: int) -> list[tuple[int, int]]:
    lo, hi = data.manifest["splits"]["test"]
    bins = 86400 // cfg["bin_seconds"]
    starts = [k for k in range(lo + cfg["lookback"], hi - bins - cfg["horizon"] + 2)
              if data.times[k] == data.times[k].astype("datetime64[D]")
              and np.all(np.diff(data.times[k-cfg["lookback"]:k+bins+cfg["horizon"]-1])
                         == np.timedelta64(cfg["bin_seconds"], "s"))]
    if len(starts) < count:
        raise ValueError(f"Only {len(starts)} complete test days; requested {count}")
    return [(s, s+bins) for s in starts[:count]]
