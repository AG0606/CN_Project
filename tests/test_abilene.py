"""Boundary checks for the five-minute, 12-router secondary experiment."""

from __future__ import annotations

import gzip

import numpy as np
import torch

from carbonroute.abilene import LB_MWH_TO_G_KWH, read_week
from carbonroute.network import Network
from carbonroute.prediction import DemandNet
from carbonroute.routing import Planner


def test_real_od_field_and_five_minute_units(tmp_path):
    # Distinct alternatives catch accidentally using a gravity-estimated column.
    fields = np.tile([375000, 9, 8, 7, 6], 144)
    source = tmp_path / "X01.gz"
    with gzip.open(source, "wt") as stream:
        line = " ".join(map(str, fields)) + "\n"
        stream.write(line * 2016)
    times, rates = read_week(source, "2004-03-01")
    assert rates.shape == (2016, 12, 12)
    assert rates[0, 0, 0] == 1.0
    assert times[1] - times[0] == np.timedelta64(5, "m")
    assert times[-1] == np.datetime64("2004-03-07T23:55")


def test_twelve_router_prediction_and_routing_shapes():
    n = 12
    edges = [(i, i + 1) for i in range(n - 1)] + [(0, n - 1)]
    network = Network([(-120 + i, 40) for i in range(n)], edges,
                      [str(i) for i in range(len(edges))], 10, 1.3, .15,
                      tuple(f"r{i}" for i in range(n)), tuple("US" for _ in range(n)))
    mask = np.zeros((n, n), dtype=np.float32)
    mask[0, 4] = 1
    model = DemandNet(network.adjacency(), mask, 8, 3)
    output = model(torch.ones((2, 12, n, n)))
    assert output.shape == (2, 3, n, n)
    assert torch.all(output * torch.tensor(mask == 0) == 0)
    cfg = {"candidate_paths": 2, "delay_stretch": 100, "hold_bins": 2,
           "horizon": 3, "utilization_limit": .8, "min_improvement": .05}
    planner = Planner(network, [(0, 4)], cfg, "reactive_carbon")
    decision = planner.decide(np.ones((3, n, n)), np.ones(n), 0)
    assert decision.routes[0][0] == 0 and decision.routes[0][-1] == 4


def test_epa_unit_conversion():
    assert abs(1000 * LB_MWH_TO_G_KWH - 453.59237) < 1e-9
