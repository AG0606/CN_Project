"""Small serialization and reproducibility utilities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def config(path: Path | None = None) -> dict[str, Any]:
    cfg = load_json(path or ROOT / "configs/default.json")
    for key in ("capacity_mbps", "bin_seconds", "lookback", "horizon", "epochs"):
        if cfg[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if cfg["bin_seconds"] not in (300, 900):
        raise ValueError("Supported source traffic resolutions are 300 and 900 seconds")
    if not 0 < cfg["margin_quantile"] < 1 or not 0 < cfg["utilization_limit"] <= 1:
        raise ValueError("Invalid margin quantile or utilization limit")
    return cfg


def finite_nonnegative(array: np.ndarray, name: str) -> None:
    if not np.isfinite(array).all() or (array < 0).any():
        raise ValueError(f"{name} must contain finite, nonnegative values")
