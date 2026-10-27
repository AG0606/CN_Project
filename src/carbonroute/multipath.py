"""Fractional path routing and a common per-OD max-min fluid service model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linprog

from .common import finite_nonnegative
from .network import Network, Pair


def fractional_service(demand: np.ndarray, incidence: np.ndarray,
                       capacity: np.ndarray) -> np.ndarray:
    """Equal-rate fairness between OD aggregates, with fixed fractions on their paths.

    One OD's path fractions form a single column. Separate subpaths never earn
    extra fairness shares. One-hot fractions reproduce the existing allocator.
    """
    finite_nonnegative(demand, "demand")
    finite_nonnegative(incidence, "fractional incidence")
    finite_nonnegative(capacity, "capacity")
    if (incidence.shape != (len(capacity), len(demand)) or
            (incidence > 1 + 1e-9).any() or (incidence.sum(axis=0) <= 0).any()):
        raise ValueError("Invalid fractional link-by-OD matrix")
    served = np.zeros_like(demand, dtype=float)
    active = demand > 1e-10
    for _ in range(len(demand) + len(capacity) + 1):
        if not active.any():
            break
        users = incidence[:, active].sum(axis=1)
        residual = np.maximum(capacity - incidence @ served, 0)
        used = users > 1e-12
        delta = min(float((demand-served)[active].min()),
                    float((residual[used]/users[used]).min()))
        served[active] += max(delta, 0)
        saturated = incidence @ served >= capacity - 1e-9
        blocked = (incidence[saturated] > 1e-12).any(axis=0)
        active &= (served < demand - 1e-9) & ~blocked
    if active.any():
        raise RuntimeError("Fractional progressive filling did not converge")
    return np.minimum(served, demand)


class Paths:
    def __init__(self, network: Network, pairs: list[Pair], cfg: dict[str, Any]):
        self.network, self.pairs = network, pairs
        self.candidates = network.candidates(pairs, cfg["candidate_paths"], cfg["delay_stretch"])
        self.routes = [route for options in self.candidates for route in options]
        self.owners = np.array([i for i, options in enumerate(self.candidates) for _ in options])
        self.membership = (np.arange(len(pairs))[:, None] == self.owners).astype(float)
        self.incidence = network.incidence(self.routes)
        self.delays = np.array([network.delay(route) for route in self.routes])

    def validate(self, weights: np.ndarray) -> None:
        if weights.shape != (len(self.routes),):
            raise ValueError("Invalid split shape")
        finite_nonnegative(weights, "path fractions")
        if not np.allclose(self.membership @ weights, 1, atol=1e-8, rtol=0):
            raise ValueError("Every OD must route exactly 100% of offered traffic")

    def effective(self, weights: np.ndarray) -> np.ndarray:
        self.validate(weights)
        return (self.incidence * weights) @ self.membership.T

    def one_hot(self, routes) -> np.ndarray:
        weights = np.zeros(len(self.routes))
        for f, route in enumerate(routes):
            options = [p for p, owner in enumerate(self.owners) if owner == f and self.routes[p] == tuple(route)]
            if len(options) != 1:
                raise ValueError("Route outside shared candidate set")
            weights[options[0]] = 1
        return weights

    def quantize(self, weights: np.ndarray, buckets: int) -> np.ndarray:
        if buckets < 1:
            raise ValueError("Buckets must be positive")
        self.validate(weights)
        result = np.zeros_like(weights)
        for f in range(len(self.pairs)):
            indices = np.flatnonzero(self.owners == f)
            values = weights[indices] * buckets
            counts = np.floor(values).astype(int)
            remainder = buckets - int(counts.sum())
            order = np.argsort(-(values-counts), kind="stable")
            counts[order[:remainder]] += 1
            result[indices] = counts / buckets
        self.validate(result)
        return result


@dataclass
class SplitDecision:
    weights: np.ndarray
    minimum_peak: float
    peak_limit: float
    projected_peak: float
    changes: int
    redistributed_mass: float


class MultipathPlanner:
    """Minimize peak offered utilization, then carbon, then split churn.

    Carbon mode allows the standard 80% guard when the optimum is below it;
    TE mode retains the minimum peak. Both retain all offered traffic, never
    optimize an admission/drop decision, and commit before actual demand is seen.
    """

    def __init__(self, paths: Paths, cfg: dict[str, Any], carbon_aware: bool = True,
                 buckets: int | None = None):
        self.paths, self.cfg, self.carbon_aware, self.buckets = paths, cfg, carbon_aware, buckets
        self.current = paths.one_hot([options[0] for options in paths.candidates])

    @staticmethod
    def solve(cost, **kwargs):
        answer = linprog(cost, method="highs", options={"time_limit": 10.0}, **kwargs)
        if not answer.success:
            raise RuntimeError(f"Multipath LP failed: {answer.message}")
        return answer

    def decide(self, forecast: np.ndarray, carbon: np.ndarray) -> SplitDecision:
        paths = self.paths
        n, horizon = paths.network.node_count, self.cfg["horizon"]
        if forecast.shape != (horizon, n, n) or carbon.shape != (n,):
            raise ValueError("Forecast/carbon shape mismatch")
        finite_nonnegative(forecast, "forecast")
        finite_nonnegative(carbon, "carbon")
        demand = forecast[:, [a for a, _ in paths.pairs], [b for _, b in paths.pairs]]
        # Envelope is conservative for every horizon using one committed split.
        envelope = demand.max(axis=0)
        load = paths.incidence * envelope[paths.owners]
        p = len(paths.routes)
        capacity = paths.network.capacities
        first = self.solve(np.r_[np.zeros(p), 1.0],
                           A_ub=np.c_[load, -capacity], b_ub=np.zeros(len(capacity)),
                           A_eq=np.c_[paths.membership, np.zeros(len(paths.pairs))],
                           b_eq=np.ones(len(paths.pairs)), bounds=[(0, 1)]*p+[(0, None)])
        minimum = float(first.x[-1])
        limit = max(self.cfg["utilization_limit"], minimum) if self.carbon_aware else minimum
        rhs = capacity * (limit + 1e-8)
        senders = np.array([a for a, _ in paths.network.arcs])
        cost = paths.incidence.T @ carbon[senders] * demand.mean(axis=0)[paths.owners]
        constraints, bounds = [load], [rhs]
        if self.carbon_aware:
            second = self.solve(cost, A_ub=load, b_ub=rhs, A_eq=paths.membership,
                                b_eq=np.ones(len(paths.pairs)), bounds=(0, 1))
            constraints.append(cost[None])
            bounds.append(np.array([float(second.fun) + 1e-8 * max(1.0, abs(float(second.fun)))]))
        # Final LP minimizes L1 change within the fixed congestion/carbon optima.
        a = np.vstack(constraints)
        b = np.concatenate(bounds)
        third = self.solve(np.r_[np.zeros(p), np.ones(p)],
                           A_ub=np.vstack([np.c_[a, np.zeros((len(a), p))],
                                           np.c_[np.eye(p), -np.eye(p)],
                                           np.c_[-np.eye(p), -np.eye(p)]]),
                           b_ub=np.r_[b, self.current, -self.current],
                           A_eq=np.c_[paths.membership, np.zeros_like(paths.membership)],
                           b_eq=np.ones(len(paths.pairs)), bounds=[(0, 1)]*p+[(0, None)]*p)
        weights = np.maximum(third.x[:p], 0)
        # Remove solver-scale roundoff, not material route fractions.
        weights /= (paths.membership @ weights)[paths.owners]
        if self.buckets is not None:
            weights = paths.quantize(weights, self.buckets)
        delta = np.abs(weights-self.current)
        changes = int(np.sum(paths.membership @ delta > 1e-6))
        peak = float((load @ weights / capacity).max())
        self.current = weights.copy()
        return SplitDecision(weights, minimum, limit, peak, changes, float(delta.sum()/2))
