"""The exact retained SNDlib graph and its explicitly assumed physical parameters."""

from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass
from typing import Any

import networkx as nx
import numpy as np

from .common import fingerprint

NODE_IDS = ("fr1.fr", "de1.de", "be1.be", "nl1.nl", "ch1.ch", "it1.it", "at1.at", "lu1.lu")
COUNTRIES = ("FR", "DE", "BE", "NL", "CH", "IT", "AT", "LU")
EXPECTED_EDGES = {
    (0, 1), (0, 2), (0, 4), (0, 7), (2, 3), (2, 7),
    (1, 3), (4, 5), (1, 5), (4, 6), (1, 6),
}

Pair = tuple[int, int]
Route = tuple[int, ...]


def section(text: str, name: str) -> list[str]:
    match = re.search(rf"^{name}\s*\(\s*\n(.*?)^\)", text, re.M | re.S)
    if not match:
        raise ValueError(f"Missing SNDlib {name} section")
    return [s.strip() for s in match.group(1).splitlines() if s.strip() and not s.lstrip().startswith("#")]


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(h, 1)))


@dataclass
class Network:
    coordinates: list[tuple[float, float]]
    physical_edges: list[Pair]
    source_link_ids: list[str]
    capacity_mbps: float
    fiber_stretch: float
    router_delay_ms: float

    def __post_init__(self) -> None:
        self.arcs = sorted([arc for a, b in self.physical_edges for arc in [(a, b), (b, a)]])
        self.arc_index = {arc: i for i, arc in enumerate(self.arcs)}
        self.capacities = np.full(len(self.arcs), self.capacity_mbps)
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from(range(len(NODE_IDS)))
        for a, b in self.arcs:
            delay = distance_km(self.coordinates[a], self.coordinates[b]) * self.fiber_stretch / 200
            self.graph.add_edge(a, b, delay_ms=delay + self.router_delay_ms)

    @classmethod
    def from_source(cls, text: str, cfg: dict[str, Any]) -> Network:
        coords = {}
        for line in section(text, "NODES"):
            fields = line.replace("(", " ").replace(")", " ").split()
            coords[fields[0]] = (float(fields[1]), float(fields[2]))
        edges, identifiers = [], []
        for line in section(text, "LINKS"):
            fields = line.replace("(", " ").replace(")", " ").split()
            if fields[1] in NODE_IDS and fields[2] in NODE_IDS:
                a, b = sorted((NODE_IDS.index(fields[1]), NODE_IDS.index(fields[2])))
                edges.append((a, b))
                identifiers.append(fields[0])
        if set(edges) != EXPECTED_EDGES or len(edges) != 11:
            raise ValueError("Source is not the agreed eleven-link GEANT subgraph")
        return cls([coords[node] for node in NODE_IDS], edges, identifiers,
                   cfg["capacity_mbps"], cfg["fiber_stretch"], cfg["router_delay_ms"])

    def metadata(self) -> dict[str, Any]:
        return {"node_ids": list(NODE_IDS), "countries": list(COUNTRIES),
                "coordinates": self.coordinates, "physical_edges": self.physical_edges,
                "source_link_ids": self.source_link_ids, "capacity_mbps": self.capacity_mbps,
                "fiber_stretch": self.fiber_stretch, "router_delay_ms": self.router_delay_ms,
                "arcs": self.arcs, "delays_ms": [self.delay((a, b)) for a, b in self.arcs]}

    @property
    def graph_hash(self) -> str:
        return fingerprint(self.metadata())

    def delay(self, route: Route) -> float:
        return sum(self.graph[a][b]["delay_ms"] for a, b in zip(route, route[1:]))

    def candidates(self, pairs: list[Pair], count: int, stretch: float) -> list[list[Route]]:
        result = []
        for a, b in pairs:
            paths = [tuple(p) for p in itertools.islice(
                nx.shortest_simple_paths(self.graph, a, b, weight="delay_ms"), count)]
            bound = self.delay(paths[0]) * stretch
            result.append([p for p in paths if self.delay(p) <= bound + 1e-9])
        return result

    def incidence(self, routes: list[Route]) -> np.ndarray:
        matrix = np.zeros((len(self.arcs), len(routes)))
        for j, path in enumerate(routes):
            for arc in zip(path, path[1:]):
                matrix[self.arc_index[arc], j] = 1
        return matrix

    def adjacency(self) -> np.ndarray:
        a = nx.to_numpy_array(self.graph, nodelist=range(8)) + np.eye(8)
        degree = np.sqrt(a.sum(axis=1))
        return (a / degree[:, None] / degree[None, :]).astype(np.float32)
