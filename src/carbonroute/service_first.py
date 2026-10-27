"""Service-first joint routing using forecast-only, max-min allocation."""
from __future__ import annotations

import numpy as np

from .common import finite_nonnegative
from .routing import BudgetPlanner, Decision


def batch_progressive_fill(demand: np.ndarray, incidence: np.ndarray,
                           capacity: np.ndarray) -> np.ndarray:
    """The same equal-rate allocator as progressive_fill, over assignment/horizon batches."""
    demand = np.asarray(demand, dtype=float)
    incidence = np.asarray(incidence, dtype=float)
    capacity = np.asarray(capacity, dtype=float)
    if demand.ndim != 3 or incidence.ndim != 3:
        raise ValueError("Expected demand [assignments,horizons,flows] and incidence [assignments,links,flows]")
    a, _, f = demand.shape
    if incidence.shape != (a, len(capacity), f) or not np.isin(incidence, [0, 1]).all():
        raise ValueError("Mismatched or non-binary incidence")
    finite_nonnegative(demand, "predicted demand")
    finite_nonnegative(capacity, "capacity")
    if (incidence.sum(axis=1) == 0).any():
        raise ValueError("Every flow must traverse a link")
    served = np.zeros_like(demand)
    active = demand > 1e-10
    for _ in range(f + len(capacity) + 1):
        if not active.any():
            break
        users = np.einsum("alf,ahf->ahl", incidence, active, optimize=True)
        residual = np.maximum(capacity - np.einsum("alf,ahf->ahl", incidence, served, optimize=True), 0)
        link_delta = np.divide(residual, users, out=np.full_like(residual, np.inf), where=users > 0)
        flow_delta = np.where(active, demand-served, np.inf)
        delta = np.minimum(link_delta.min(axis=2), flow_delta.min(axis=2))
        delta = np.where(active.any(axis=2), np.maximum(delta, 0), 0)
        served += active * delta[:, :, None]
        saturated = np.einsum("alf,ahf->ahl", incidence, served, optimize=True) >= capacity - 1e-9
        blocked = np.einsum("alf,ahl->ahf", incidence, saturated, optimize=True) > 0
        active &= (served < demand - 1e-9) & ~blocked
    if active.any():
        raise RuntimeError("Batched progressive filling did not converge")
    return np.minimum(served, demand)


class ServiceFirstPlanner(BudgetPlanner):
    """Maximize modeled service, then minimize carbon score within a fixed service tolerance."""

    def __init__(self, network, pairs, cfg, service_tolerance: float = 0.001):
        super().__init__(network, pairs, cfg)
        if not 0 <= service_tolerance <= 1:
            raise ValueError("Service tolerance must be between zero and one")
        self.service_tolerance = service_tolerance

    def decide(self, forecast: np.ndarray, current_carbon: np.ndarray, step: int,
               reactive_forecast: np.ndarray) -> Decision:
        n, horizon = self.network.node_count, self.cfg["horizon"]
        if forecast.shape != (horizon, n, n) or current_carbon.shape != (n,):
            raise ValueError("Forecast/carbon shape mismatch")
        finite_nonnegative(forecast, "forecast")
        finite_nonnegative(current_carbon, "carbon")
        demand = forecast[:, [a for a, _ in self.pairs], [b for _, b in self.pairs]]
        demand_batch = np.broadcast_to(demand, (len(self.assignments), *demand.shape))
        served = batch_progressive_fill(demand_batch, self.incidence, self.network.capacities)
        totals = served.sum(axis=(1, 2))
        eligible = totals >= totals.max() - self.service_tolerance * demand.sum() - 1e-9
        costs = np.einsum("afi,i->af", self.sender_counts, current_carbon)
        weighted = np.einsum("ahf,af->a", served, costs)
        scores = np.divide(weighted, totals, out=np.zeros_like(totals), where=totals > 0)
        changes = np.count_nonzero(self.choices != self.choices[self.current], axis=1)
        pool = np.flatnonzero(eligible)
        chosen = int(min(pool, key=lambda i: (scores[i], changes[i], self.delay[i], i)))
        changed = self.choices[chosen] != self.choices[self.current]
        self.current = chosen
        util = np.einsum("hf,lf->hl", demand, self.incidence[chosen]) / self.network.capacities
        infeasible = sum(bool(util[:, self.incidence[chosen, :, f] > 0].max()
                              > self.cfg["utilization_limit"] + 1e-9)
                         for f in range(len(self.pairs)))
        reasons = tuple("service-first" if flag else "kept" for flag in changed)
        return Decision(self.assignments[chosen], int(changed.sum()), infeasible,
                        float(util.max()), reasons, joint_assignments_evaluated=len(self.assignments))
