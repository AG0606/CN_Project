"""Verified downloads, chronological traffic preparation and daily carbon pairing."""

from __future__ import annotations

import hashlib
import tarfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import fingerprint, finite_nonnegative, load_json, save_json, sha256
from .network import COUNTRIES, NODE_IDS, Network, Pair, section

SOURCES = {
    "geant.txt": ("https://sndlib.put.poznan.pl/download/sndlib-networks-native/geant.txt",
                  "11b943a4330105aaa368dae1a8e6a335"),
    "geant-traffic.tgz": (
        "https://sndlib.put.poznan.pl/download/directed-geant-uhlig-15min-over-4months-ALL-native.tgz",
        "6d620995ae7cce558392ac58670ba122"),
    "carbon.csv": ("https://zenodo.org/records/15987717/files/ECON-PowerCI_2015_2024.csv?download=1",
                   "7609df58ddd32362276b263c9a4517b8"),
}
ISO3 = ("FRA", "DEU", "BEL", "NLD", "CHE", "ITA", "AUT", "LUX")


def download_inputs(root: Path) -> dict[str, Any]:
    raw = root / "inputs/raw"
    raw.mkdir(parents=True, exist_ok=True)
    records = {}
    for name, (url, expected_md5) in SOURCES.items():
        path = raw / name
        if not path.exists():
            print(f"Downloading {name} ...", flush=True)
            temporary = path.with_suffix(path.suffix + ".part")
            request = urllib.request.Request(url, headers={"User-Agent": "GEANT-Carbon-Research/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 100_000_000:
                        raise ValueError("Source exceeds expected size limit")
                    out.write(chunk)
            temporary.replace(path)
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        if md5 != expected_md5:
            raise ValueError(f"Checksum mismatch: {path}. Remove that cached file and retry; do not use it.")
        records[name] = {"url": url, "bytes": path.stat().st_size, "md5": md5,
                         "sha256": sha256(path),
                         "verified_utc": datetime.now(timezone.utc).isoformat()}
    save_json(raw / "sources.json", records)
    return records


def parse_demand(text: str) -> tuple[np.datetime64, np.ndarray, int]:
    meta = dict(line.split("=", 1) for line in section(text, "META"))
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    if meta.get("unit") != "MBITPERSEC" or meta.get("granularity") != "15min":
        raise ValueError("Only dynamic fifteen-minute Mbps matrices are accepted")
    stamp = np.datetime64(datetime.strptime(meta["time"], "%Y%m%d-%H%M"), "m")
    result = np.zeros((8, 8), dtype=np.float32)
    seen: set[Pair] = set()
    for line in section(text, "DEMANDS"):
        f = line.replace("(", " ").replace(")", " ").split()
        if f[1] not in NODE_IDS or f[2] not in NODE_IDS:
            continue
        a, b = NODE_IDS.index(f[1]), NODE_IDS.index(f[2])
        if a == b or (a, b) in seen:
            raise ValueError("Duplicate or diagonal source demand")
        if float(f[3]) != 1:
            raise ValueError("Unexpected SNDlib routing unit")
        seen.add((a, b))
        result[a, b] = float(f[4])
    finite_nonnegative(result, "source demand")
    return stamp, result, 56 - len(seen)


def window_indices(times: np.ndarray, start: int, stop: int, lookback: int, horizon: int,
                   bin_seconds: int = 900) -> np.ndarray:
    """Target starts whose history AND labels stay in one contiguous split."""
    valid = [k for k in range(start + lookback, stop - horizon + 1)
             if np.all(np.diff(times[k-lookback:k+horizon]) == np.timedelta64(bin_seconds, "s"))]
    return np.array(valid, dtype=np.int64)


def read_archive(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    records: dict[np.datetime64, np.ndarray] = {}
    missing = 0
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".txt"):
                continue
            if member.size > 200_000:
                raise ValueError("Unexpected traffic member size")
            stream = archive.extractfile(member)
            if stream is None:
                continue
            stamp, matrix, omitted = parse_demand(stream.read().decode("utf-8"))
            if stamp in records:
                raise ValueError(f"Duplicate traffic timestamp: {stamp}")
            records[stamp] = matrix
            missing += omitted
    times = np.array(sorted(records), dtype="datetime64[m]")
    if not len(times):
        raise ValueError("Empty traffic archive")
    matrices = np.stack([records[t] for t in times])
    return times, matrices, {
        "archive_matrices": len(times), "archive_start": str(times[0]), "archive_end": str(times[-1]),
        "archive_gap_count": int(np.sum(np.diff(times) != np.timedelta64(15, "m"))),
        "omitted_retained_demands": missing,
        "omission_rule": "Unlisted native SNDlib OD demands are zero; missing timestamps are never filled",
        "source_timezone": "Not specified by source; preserve naive source timestamps, no UTC assertion",
    }


def choose_pairs(train: np.ndarray, network: Network, cfg: dict[str, Any]) -> list[Pair]:
    """High mean demands with route diversity, then modest shared-link preference.

    All ranking statistics come from training only; countries/carbon/test are not used.
    """
    means = train.mean(axis=0)
    eligible = [(a, b) for a in range(network.node_count)
                for b in range(network.node_count) if a != b and means[a, b] > 0]
    options = network.candidates(eligible, cfg["candidate_paths"], cfg["delay_stretch"])
    paths = {pair: routes for pair, routes in zip(eligible, options) if len(routes) >= 2}
    if len(paths) < cfg["active_pairs"]:
        raise ValueError("Insufficient pairs with two delay-feasible candidates")
    selected: list[Pair] = []
    occupied: set[Pair] = set()
    while len(selected) < cfg["active_pairs"]:
        def score(pair: Pair) -> tuple[float, int, int]:
            p = paths[pair][0]
            overlap = len(set(zip(p, p[1:])) & occupied)
            return (float(means[pair]) * (1 + 0.25 * overlap), -pair[0], -pair[1])
        pair = max((p for p in paths if p not in selected), key=score)
        selected.append(pair)
        path = paths[pair][0]
        occupied.update(zip(path, path[1:]))
    return selected


def prepare(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    sources = download_inputs(root)
    network = Network.from_source((root / "inputs/raw/geant.txt").read_text(), cfg)
    cache = root / "inputs/processed"
    cache.mkdir(parents=True, exist_ok=True)
    times, full, audit = read_archive(root / "inputs/raw/geant-traffic.tgz")
    # Earliest fixed calendar interval; selection never inspects test performance.
    last = times[0].astype("datetime64[D]") + np.timedelta64(cfg["traffic_days"], "D")
    keep = times < last
    times, full = times[keep], full[keep]
    n = len(times)
    cuts = [0, int(n * .6), int(n * .8), n]
    splits = {name: [cuts[i], cuts[i+1]] for i, name in enumerate(("train", "validation", "test"))}
    pairs = choose_pairs(full[:cuts[1]], network, cfg)
    mask = np.zeros((8, 8), dtype=np.float32)
    for a, b in pairs:
        mask[a, b] = 1
    rates = full * mask
    shortest = [p[0] for p in network.candidates(pairs, 1, 1)]
    train_rates = rates[:cuts[1], [a for a, b in pairs], [b for a, b in pairs]]
    max_load = (train_rates @ network.incidence(shortest).T).max(axis=1)
    factor = cfg["train_utilization_p95"] * network.capacity_mbps / float(np.quantile(max_load, .95))
    rates *= factor
    # Per-pair scale from training; inactive entries stay one and are always masked.
    scale = np.maximum(np.quantile(rates[:cuts[1]], .95, axis=0), 0.01).astype(np.float32)
    scale[mask == 0] = 1
    counts = {name: len(window_indices(times, lo, hi, cfg["lookback"], cfg["horizon"]))
              for name, (lo, hi) in splits.items()}
    if min(counts.values()) < 96:
        raise ValueError(f"Insufficient contiguous windows: {counts}")
    np.savez_compressed(cache / "traffic.npz", times=times, full_mbps=full,
                        rates=rates, mask=mask, scale=scale)
    metadata = {"schema_version": 1, "config_hash": fingerprint(cfg), "config": cfg,
                "sources": sources, "graph": network.metadata(), "graph_hash": network.graph_hash,
                "traffic_audit": audit, "rows": n, "start": str(times[0]), "end": str(times[-1]),
                "splits": splits, "window_counts": counts, "pairs": pairs,
                "pair_ids": [[NODE_IDS[a], NODE_IDS[b]] for a, b in pairs],
                "pair_selection": "Training mean * (1 + .25 * shortest-route overlap); >=2 delay-feasible paths",
                "traffic_factor": factor, "units": "decimal Mbps",
                "traffic_sha256": sha256(cache / "traffic.npz")}
    save_json(cache / "manifest.json", metadata)
    CarbonTable(root / "inputs/raw/carbon.csv")  # Fail early on schema/quality problems.
    print(f"Prepared {n} matrices; {counts}; six-pair rate factor {factor:.6g}", flush=True)
    return metadata


@dataclass
class Prepared:
    times: np.ndarray
    rates: np.ndarray
    mask: np.ndarray
    scale: np.ndarray
    network: Network
    pairs: list[Pair]
    manifest: dict[str, Any]


def load_prepared(root: Path, cfg: dict[str, Any]) -> Prepared:
    folder = root / "inputs/processed"
    meta = load_json(folder / "manifest.json")
    if meta["config_hash"] != fingerprint(cfg):
        raise ValueError("Configuration changed since preparation. Run prepare and train again.")
    if sha256(folder / "traffic.npz") != meta["traffic_sha256"]:
        raise ValueError("Prepared traffic checksum mismatch")
    network = Network.from_source((root / "inputs/raw/geant.txt").read_text(), cfg)
    if network.graph_hash != meta["graph_hash"]:
        raise ValueError("Graph mismatch")
    with np.load(folder / "traffic.npz", allow_pickle=False) as z:
        return Prepared(z["times"], z["rates"], z["mask"], z["scale"], network,
                        [tuple(p) for p in meta["pairs"]], meta)


class CarbonTable:
    def __init__(self, path: Path):
        self.source_hash = sha256(path)
        frame = pd.read_csv(path)
        if set(frame.columns) != {"ISO", "Country Name", "Timestamp", "Value", "FLAG"}:
            raise ValueError("Unexpected ECON-PowerCI schema")
        frame = frame[frame.ISO.isin(ISO3)].copy()
        frame["date"] = pd.to_datetime(frame.Timestamp, format="%Y/%m/%d")
        if frame.duplicated(["ISO", "date"]).any():
            raise ValueError("Duplicate country/carbon date")
        finite_nonnegative(frame.Value.dropna().to_numpy(), "carbon intensity")
        if not set(frame.FLAG.unique()) <= {"N", "F"}:
            raise ValueError("Unknown carbon quality flag")
        self.values = frame.pivot(index="date", columns="ISO", values="Value").reindex(columns=ISO3)
        self.flags = frame.pivot(index="date", columns="ISO", values="FLAG").reindex(columns=ISO3)

    def pair(self, traffic_times: np.ndarray, year: int) -> tuple[np.ndarray, list[dict[str, Any]]]:
        """Nearest same-weekday seasonal start in requested year, complete across 8 countries.

        Selection is based on calendar and availability only, never carbon contrast.
        Source traffic's naive calendar day is used; no timezone equivalence is claimed.
        """
        start = pd.Timestamp(traffic_times[0]).normalize()
        days = (traffic_times.astype("datetime64[D]") - traffic_times[0].astype("datetime64[D]")).astype(int)
        length = int(days[-1]) + 1
        target = start.replace(year=year)
        available = self.values.dropna().index
        candidates = [d for d in available if d.year == year and d.weekday() == start.weekday()
                      and abs((d-target).days) <= 21]
        candidates.sort(key=lambda d: (abs((d-target).days), d))
        for d in candidates:
            dates = pd.date_range(d, periods=length, freq="D")
            if dates.isin(available).all():
                ci = self.values.loc[dates].to_numpy(dtype=float)
                flags = self.flags.loc[dates]
                alignment = [{"traffic_day": str((start + pd.Timedelta(days=i)).date()),
                              "carbon_day": str(day.date()), "year": year,
                              "country_codes": list(COUNTRIES), "intensities": ci[i].tolist(),
                              "flags": flags.iloc[i].tolist()} for i, day in enumerate(dates)]
                return ci[days], alignment
        raise ValueError(f"No complete weekday/season carbon pairing for {start.date()} in {year}")
