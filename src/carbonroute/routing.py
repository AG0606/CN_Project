"""Deterministic candidate-path planning with shared reservations and hysteresis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import finite_nonnegative
from .network import Network, Pair, Route

POLICIES = ("shortest_path", "reactive_carbon", "predictive_te", "predictive_carbon",
            "persistence_carbon", "no_margin", "no_hysteresis")


@dataclass(frozen=True)
class Decision:
    routes: tuple[Route, ...]
    changes: int
    infeasible_pairs: int
    projected_max_utilization: float
    reasons: tuple[str, ...]


class Planner:
    def __init__(self, network: Network, pairs: list[Pair], cfg: dict[str, Any], policy: str):
        if policy not in POLICIES:
            raise ValueError(f"Unknown policy: {policy}")
        self.network, self.pairs, self.cfg, self.policy = network, pairs, cfg, policy
        self.candidates = network.candidates(pairs, cfg["candidate_paths"], cfg["delay_stretch"])
        self.routes = [paths[0] for paths in self.candidates]
        self.last_changed = np.full(len(pairs), -cfg["hold_bins"], dtype=int)
        self.vectors = [{p: network.incidence([p])[:, 0] for p in paths} for paths in self.candidates]

    def decide(self, forecast: np.ndarray, current_carbon: np.ndarray, step: int) -> Decision:
        """Receives predicted demand and current carbon ONLY; no actual future rows."""
        if forecast.shape != (self.cfg["horizon"], 8, 8) or current_carbon.shape != (8,):
            raise ValueError("Forecast/carbon shape mismatch")
        finite_nonnegative(forecast, "forecast")
        finite_nonnegative(current_carbon, "carbon")
        demand = forecast[:, [a for a, b in self.pairs], [b for a, b in self.pairs]]
        loads = demand @ self.network.incidence(self.routes).T
        if self.policy == "shortest_path":
            return Decision(tuple(self.routes), 0, 0,
                            float((loads/self.network.capacities).max()), tuple("fixed" for _ in self.pairs))
        order = sorted(range(len(self.pairs)), key=lambda i: (-float(demand[:, i].max()), i))
        changes, infeasible = 0, 0
        reasons = ["kept"] * len(self.pairs)
        limit = self.cfg["utilization_limit"]
        for i in order:
            old = self.routes[i]
            old_vector = self.vectors[i][old]
            # Remove this flow before evaluating replacements: no double reservation.
            base = loads - demand[:, i, None] * old_vector[None]
            options = []
            for path in self.candidates[i]:
                vector = self.vectors[i][path]
                projected = base + demand[:, i, None] * vector[None]
                utilization = projected / self.network.capacities
                path_max = float(utilization[:, vector > 0].max())
                global_max = float(utilization.max())
                carbon_cost = float(sum(current_carbon[node] for node in path[:-1]))
                objective = global_max if self.policy == "predictive_te" else carbon_cost
                options.append((path, path_max <= limit+1e-9, objective, global_max, path_max))
            feasible = [o for o in options if o[1]]
            if feasible:
                best = min(feasible, key=lambda o: (o[2], o[3], self.network.delay(o[0]), o[0]))
            else:
                infeasible += 1
                best = min(options, key=lambda o: (o[3], o[4], o[2], self.network.delay(o[0]), o[0]))
            current = next(o for o in options if o[0] == old)
            emergency = not current[1]
            if best[0] != old:
                improvement = (current[2]-best[2]) / max(abs(current[2]), 1e-9)
                hold = step - self.last_changed[i] < self.cfg["hold_bins"]
                if self.policy == "no_hysteresis" or emergency or (
                    not hold and improvement >= self.cfg["min_improvement"]
                ):
                    self.routes[i] = best[0]
                    self.last_changed[i] = step
                    changes += 1
                    reasons[i] = "capacity-risk" if emergency else "objective-improvement"
                else:
                    reasons[i] = "hold-time" if hold else "small-improvement"
            if not feasible:
                reasons[i] += ";no-feasible-candidate"
            loads = base + demand[:, i, None] * self.vectors[i][self.routes[i]][None]
        return Decision(tuple(self.routes), changes, infeasible,
                        float((loads/self.network.capacities).max()), tuple(reasons))
