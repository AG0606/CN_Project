"""Aggregate max-min rate service and transparent forwarding attribution."""

from __future__ import annotations

import numpy as np

from .common import finite_nonnegative


def progressive_fill(demand: np.ndarray, incidence: np.ndarray, capacity: np.ndarray) -> np.ndarray:
    """Equal-rate progressive filling; freeze a flow at demand or a saturated link.

    Columns are fixed loop-free flow routes, rows directed links. This models a
    fluid allocator, not TCP, queues, packet loss, or RTT.
    """
    finite_nonnegative(demand, "demand")
    finite_nonnegative(capacity, "capacity")
    if incidence.shape != (len(capacity), len(demand)) or not np.isin(incidence, [0, 1]).all():
        raise ValueError("Incidence must be a binary link-by-flow matrix")
    if (incidence.sum(axis=0) == 0).any():
        raise ValueError("Every flow must traverse a link")
    served = np.zeros_like(demand, dtype=float)
    active = demand > 1e-10
    for _ in range(len(demand) + len(capacity) + 1):
        if not active.any():
            break
        users = incidence[:, active].sum(axis=1)
        residual = np.maximum(capacity - incidence @ served, 0)
        used = users > 0
        delta = min(float((demand-served)[active].min()), float((residual[used]/users[used]).min()))
        served[active] += max(delta, 0)
        saturated = incidence @ served >= capacity - 1e-9
        blocked = (incidence[saturated] > 0).any(axis=0)
        active &= (served < demand - 1e-9) & ~blocked
    if active.any():
        raise RuntimeError("Progressive filling did not converge")
    return np.minimum(served, demand)


def forwarding_score(served: np.ndarray, path_cost: np.ndarray, seconds: float = 900,
                     epsilon_j_per_mb: float | None = None) -> dict[str, float | None]:
    """Byte-weighted sum of sender CI over hops; no energy savings implied.

    Score units: g CO2/kWh summed over forwarding hops (equal hop-energy
    assumption). Absolute CO2 exists only when an explicit J/MB coefficient is supplied.
    """
    finite_nonnegative(served, "served")
    finite_nonnegative(path_cost, "path_cost")
    if seconds <= 0 or (epsilon_j_per_mb is not None and epsilon_j_per_mb < 0):
        raise ValueError("Duration must be positive and energy coefficient nonnegative")
    mb = served * seconds / 8
    numerator = float(mb @ path_cost)
    total = float(mb.sum())
    return {"served_mb": total, "carbon_weighted_mb": numerator,
            "forwarding_score": numerator / total if total else None,
            "modeled_co2_g": None if epsilon_j_per_mb is None else numerator * epsilon_j_per_mb / 3_600_000}


def power_model_grams(outgoing_served_mbps: np.ndarray, carbon: np.ndarray, seconds: float,
                      idle_w: float, beta_w_per_mbps: float) -> float:
    """Optional hypothetical all-routers-on model; not measured energy."""
    finite_nonnegative(outgoing_served_mbps, "served load")
    finite_nonnegative(carbon, "carbon intensity")
    if min(idle_w, beta_w_per_mbps) < 0 or seconds <= 0:
        raise ValueError("Invalid power model parameters")
    power = idle_w + beta_w_per_mbps * outgoing_served_mbps
    return float(np.sum(power * carbon) * seconds / 3_600_000)
