"""Small dense GCN + GRU, matched no-graph GRU, and persistence comparison."""

from __future__ import annotations

import copy
import random
import time
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .common import fingerprint, load_json, save_json, sha256
from .data import Prepared, load_prepared, window_indices


class Predictor(Protocol):
    margin: np.ndarray

    def predict(self, history: np.ndarray) -> np.ndarray:
        """History only, ending before the target; output [horizon, node, destination]."""
        ...


class DemandNet(nn.Module):
    adjacency: torch.Tensor
    mask: torch.Tensor
    def __init__(self, adjacency: np.ndarray, mask: np.ndarray, hidden: int, horizon: int):
        super().__init__()
        self.horizon = horizon
        self.node_count = mask.shape[0]
        if mask.shape != adjacency.shape or mask.ndim != 2:
            raise ValueError("Mask and adjacency must be square and have matching dimensions")
        self.register_buffer("adjacency", torch.tensor(adjacency, dtype=torch.float32))
        self.register_buffer("mask", torch.tensor(mask, dtype=torch.float32))
        # Preserve local OD information alongside neighbor-aggregated information.
        self.spatial = nn.Linear(2 * self.node_count, hidden)
        self.temporal = nn.GRU(hidden, hidden, batch_first=True)
        self.head = nn.Linear(hidden, horizon * self.node_count)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, steps, nodes, _ = x.shape
        neighbors = torch.einsum("ij,btjf->btif", self.adjacency, x)
        embedded = torch.relu(self.spatial(torch.cat((x, neighbors), dim=-1)))
        sequence = embedded.permute(0, 2, 1, 3).reshape(batch * nodes, steps, -1)
        _, hidden = self.temporal(sequence)
        correction = self.head(hidden[-1]).reshape(
            batch, nodes, self.horizon, self.node_count).permute(0, 2, 1, 3)
        # Residual forecast starts from persistence; learned corrections can go either way.
        return torch.clamp(x[:, -1:, :, :] + correction, min=0) * self.mask


class Persistence:
    def __init__(self, horizon: int, mask: np.ndarray, margin: np.ndarray | None = None):
        self.horizon, self.mask = horizon, mask
        self.margin = np.zeros((horizon, *mask.shape)) if margin is None else margin

    def predict(self, history: np.ndarray) -> np.ndarray:
        if len(history) == 0:
            raise ValueError("Persistence needs at least one observation")
        return np.repeat(history[-1:]*self.mask, self.horizon, axis=0)


class TrainedPredictor:
    def __init__(self, folder: Path, prepared: Prepared, cfg: dict[str, Any], kind: str = "gnn"):
        meta = load_json(folder / f"{kind}.json")
        if meta["config_hash"] != fingerprint(cfg) or meta["traffic_sha256"] != prepared.manifest["traffic_sha256"]:
            raise ValueError("Checkpoint configuration or training data mismatch; retrain")
        if meta["graph_hash"] != prepared.network.graph_hash:
            raise ValueError("Checkpoint graph mismatch")
        if sha256(folder / f"{kind}.pt") != meta["checkpoint_sha256"]:
            raise ValueError("Checkpoint checksum mismatch")
        torch.set_num_threads(cfg["cpu_threads"])
        n = prepared.network.node_count
        adjacency = prepared.network.adjacency() if kind == "gnn" else np.eye(n, dtype=np.float32)
        self.model = DemandNet(adjacency, prepared.mask, cfg["hidden_size"], cfg["horizon"])
        self.model.load_state_dict(torch.load(folder / f"{kind}.pt", map_location="cpu", weights_only=True))
        self.model.eval()
        self.scale = prepared.scale
        self.lookback = cfg["lookback"]
        self.node_count = n
        self.margin = np.array(meta["margin_mbps"], dtype=np.float32)

    def predict(self, history: np.ndarray) -> np.ndarray:
        if history.shape != (self.lookback, self.node_count, self.node_count):
            raise ValueError(f"Expected exactly {self.lookback} historical matrices")
        with torch.inference_mode():
            x = torch.tensor(history[None] / self.scale, dtype=torch.float32)
            return self.model(x)[0].numpy() * self.scale


def make_windows(data: Prepared, cfg: dict[str, Any], split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lo, hi = data.manifest["splits"][split]
    indices = window_indices(data.times, lo, hi, cfg["lookback"], cfg["horizon"],
                             cfg["bin_seconds"])
    x = np.stack([data.rates[k-cfg["lookback"]:k] for k in indices])
    y = np.stack([data.rates[k:k+cfg["horizon"]] for k in indices])
    return x, y, indices


def batch_prediction(model: DemandNet, x: np.ndarray, scale: np.ndarray, batch_size: int) -> np.ndarray:
    model.eval()
    chunks = []
    with torch.inference_mode():
        for start in range(0, len(x), batch_size):
            chunks.append(model(torch.tensor(x[start:start+batch_size] / scale,
                                             dtype=torch.float32)).numpy() * scale)
    return np.concatenate(chunks)


def calibrate_margin(actual: np.ndarray, predicted: np.ndarray, mask: np.ndarray, q: float) -> np.ndarray:
    """Per-horizon positive validation residual quantile, pooled across active pairs."""
    residual = np.maximum(actual-predicted, 0)[:, :, mask.astype(bool)]
    quantiles = np.quantile(residual, q, axis=(0, 2))
    return quantiles[:, None, None] * mask[None]


def forecast_metrics(actual: np.ndarray, predicted: np.ndarray, margin: np.ndarray,
                     mask: np.ndarray, high_threshold: float) -> list[dict[str, Any]]:
    rows = []
    for h in range(actual.shape[1]):
        y, p = actual[:, h, mask.astype(bool)], predicted[:, h, mask.astype(bool)]
        error = np.abs(y-p)
        high = y >= high_threshold
        rows.append({"horizon_bins": h+1, "mae_mbps": float(error.mean()),
                     "rmse_mbps": float(np.sqrt(np.mean((y-p)**2))),
                     "high_load_mae_mbps": float(error[high].mean()) if high.any() else None,
                     "high_load_threshold_mbps": high_threshold,
                     "upper_margin_coverage": float(np.mean(y <= p+margin[h, mask.astype(bool)])),
                     "points": int(y.size)})
    return rows


def link_aware_loss(error_mbps: torch.Tensor, actual_mbps: torch.Tensor,
                    active: torch.Tensor, pairs: list[tuple[int, int]],
                    incidence: torch.Tensor, capacities: torch.Tensor,
                    alpha: float) -> torch.Tensor:
    """OD MAE plus a shortest-path link-load error proxy, not differentiable routing.

    Actual link utilization weights are computed only from the batch targets.
    The declared training and validation batches never contain final test rows.
    """
    if alpha < 0:
        raise ValueError("Routing loss weight must be nonnegative")
    base = error_mbps[:, :, active].abs().mean()
    if alpha == 0:
        return base
    sources, targets = zip(*pairs)
    flow_error = error_mbps[:, :, list(sources), list(targets)]
    actual = actual_mbps[:, :, list(sources), list(targets)]
    link_error = torch.einsum("bhf,lf->bhl", flow_error, incidence)
    actual_load = torch.einsum("bhf,lf->bhl", actual, incidence)
    weights = 1 + torch.clamp(actual_load / capacities, min=0, max=2)
    return base + alpha * (weights * link_error.abs()).sum() / weights.sum()


def train(root: Path, cfg: dict[str, Any], prepared: Prepared | None = None,
          artifact_dir: Path | None = None, evaluate_test: bool = True) -> dict[str, Any]:
    data = prepared if prepared is not None else load_prepared(root, cfg)
    folder = artifact_dir or root / "artifacts"
    folder.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(cfg["cpu_threads"])
    torch.use_deterministic_algorithms(True)
    xtrain, ytrain, _ = make_windows(data, cfg, "train")
    xval, yval, _ = make_windows(data, cfg, "validation")
    test = make_windows(data, cfg, "test") if evaluate_test else None
    alpha = float(cfg.get("routing_loss_alpha", 0))
    if alpha < 0:
        raise ValueError("Routing loss weight must be nonnegative")
    shortest = [p[0] for p in data.network.candidates(data.pairs, 1, 1)]
    loss_incidence = torch.tensor(data.network.incidence(shortest), dtype=torch.float32)
    loss_capacities = torch.tensor(data.network.capacities, dtype=torch.float32)
    high_threshold = float(np.quantile(ytrain[:, :, data.mask.astype(bool)], .9))
    logs: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    for kind in ("gnn", "gru"):
        random.seed(cfg["seed"])
        np.random.seed(cfg["seed"])
        torch.manual_seed(cfg["seed"])
        adjacency = (data.network.adjacency() if kind == "gnn" else
                     np.eye(data.network.node_count, dtype=np.float32))
        model = DemandNet(adjacency, data.mask, cfg["hidden_size"], cfg["horizon"])
        optimizer = torch.optim.Adam(model.parameters(), lr=cfg["learning_rate"])
        loader = DataLoader(TensorDataset(torch.tensor(xtrain / data.scale, dtype=torch.float32),
                                         torch.tensor(ytrain / data.scale, dtype=torch.float32)),
                            batch_size=cfg["batch_size"], shuffle=True, num_workers=0,
                            generator=torch.Generator().manual_seed(cfg["seed"]))
        active = torch.tensor(data.mask.astype(bool))
        scale_t = torch.tensor(data.scale)
        best, best_epoch, stale = float("inf"), 0, 0
        best_state = copy.deepcopy(model.state_dict())
        started = time.perf_counter()
        for epoch in range(1, cfg["epochs"] + 1):
            model.train()
            loss_sum = 0.0
            mae_sum = 0.0
            for x, y in loader:
                optimizer.zero_grad()
                prediction = model(x)
                loss = link_aware_loss((prediction-y)*scale_t, y*scale_t, active,
                                       data.pairs, loss_incidence, loss_capacities, alpha)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1)
                optimizer.step()
                loss_sum += float(loss.detach()) * len(x)
                mae_sum += float(((prediction-y)*scale_t)[:, :, active].abs().mean().detach()) * len(x)
            val = batch_prediction(model, xval, data.scale, cfg["batch_size"])
            raw_mae = float(np.abs(val-yval)[:, :, data.mask.astype(bool)].mean())
            score = raw_mae if alpha == 0 else float(link_aware_loss(
                torch.tensor(val-yval), torch.tensor(yval), active, data.pairs,
                loss_incidence, loss_capacities, alpha))
            logs.append({"model": kind, "epoch": epoch, "train_mae_mbps": mae_sum/len(xtrain),
                         "train_objective": loss_sum/len(xtrain),
                         "validation_mae_mbps": raw_mae, "validation_selection_loss": score,
                         "routing_loss_alpha": alpha})
            if score < best - 1e-6:
                best, best_epoch, stale = score, epoch, 0
                best_state = copy.deepcopy(model.state_dict())
            else:
                stale += 1
            if epoch == 1 or epoch % 5 == 0 or stale >= cfg["patience"]:
                print(f"{kind} epoch {epoch}: validation MAE {raw_mae:.4f} Mbps; selection loss {score:.4f}", flush=True)
            if stale >= cfg["patience"]:
                break
        model.load_state_dict(best_state)
        torch.save(model.state_dict(), folder / f"{kind}.pt")
        val = batch_prediction(model, xval, data.scale, cfg["batch_size"])
        margin = calibrate_margin(yval, val, data.mask, cfg["margin_quantile"])
        info = {"model": kind, "architecture": "local + normalized adjacency GCN, shared node GRU, residual head"
                if kind == "gnn" else "same parameters with identity adjacency; no neighbor communication",
                "parameters": sum(p.numel() for p in model.parameters()),
                "config_hash": fingerprint(cfg), "graph_hash": data.network.graph_hash,
                "traffic_sha256": data.manifest["traffic_sha256"],
                "checkpoint_sha256": sha256(folder / f"{kind}.pt"), "seed": cfg["seed"],
                "best_epoch": best_epoch,
                "validation_mae_mbps": float(np.abs(val-yval)[:, :, data.mask.astype(bool)].mean()),
                "validation_selection_loss": best, "routing_loss_alpha": alpha,
                "training_seconds": time.perf_counter()-started,
                "margin_mbps": margin.tolist(), "node_ids": data.manifest["graph"]["node_ids"],
                "pairs": data.manifest["pairs"], "scale": data.scale.tolist()}
        save_json(folder / f"{kind}.json", info)
        metadata[kind] = info
        evaluation = [("validation", xval, yval)]
        if test is not None:
            xtest, ytest, test_indices = test
            evaluation.append(("test", xtest, ytest))
        for split, x, y in evaluation:
            p = batch_prediction(model, x, data.scale, cfg["batch_size"])
            metrics.extend({"model": kind, "split": split, **row} for row in
                           forecast_metrics(y, p, margin, data.mask, high_threshold))
            if split == "test":
                np.savez_compressed(folder / f"{kind}_test_forecasts.npz", indices=test_indices,
                                    actual=y, predicted=p)
    val_p = np.repeat(xval[:, -1:, :, :], cfg["horizon"], axis=1)
    persistence_margin = calibrate_margin(yval, val_p, data.mask, cfg["margin_quantile"])
    save_json(folder / "persistence.json", {"margin_mbps": persistence_margin.tolist(),
                                           "config_hash": fingerprint(cfg),
                                           "traffic_sha256": data.manifest["traffic_sha256"]})
    evaluation = [("validation", xval, yval)]
    if test is not None:
        xtest, ytest, _ = test
        evaluation.append(("test", xtest, ytest))
    for split, x, y in evaluation:
        p = np.repeat(x[:, -1:, :, :], cfg["horizon"], axis=1)
        metrics.extend({"model": "persistence", "split": split, **row} for row in
                       forecast_metrics(y, p, persistence_margin, data.mask, high_threshold))
    pd.DataFrame(logs).to_csv(folder / "training.csv", index=False)
    pd.DataFrame(metrics).to_csv(folder / "forecast_metrics.csv", index=False)
    save_json(folder / "training_summary.json", {"config": cfg, "models": metadata,
                                                "test_evaluated": evaluate_test,
                                                "torch_version": torch.__version__})
    return metadata
