import numpy as np
from test_routing import network

from carbonroute.common import config
from carbonroute.data import Prepared
from carbonroute.prediction import Persistence
from carbonroute.service import progressive_fill
from carbonroute.service_first import ServiceFirstPlanner, batch_progressive_fill
from carbonroute.service_first_simulation import replay


def test_batched_service_matches_original_progressive_fill():
    rng = np.random.default_rng(45)
    incidence = np.array([[[1, 1, 0], [0, 1, 1]], [[1, 0, 1], [0, 1, 0]]])
    demand = rng.uniform(0, 20, size=(2, 5, 3))
    demand[0, 0] = 0
    capacity = np.array([10., 7.])
    actual = batch_progressive_fill(demand, incidence, capacity)
    for a in range(2):
        for h in range(5):
            np.testing.assert_allclose(actual[a, h], progressive_fill(demand[a, h], incidence[a], capacity))


def test_planner_prefers_served_traffic_before_clean_bottleneck():
    cfg = config()
    cfg.update(delay_stretch=10)
    graph = network()
    pairs = [(0, 3), (2, 3)]
    forecast = np.zeros((3, 8, 8))
    forecast[:, 0, 3] = 8
    forecast[:, 2, 3] = 8
    ci = np.array([1, 500, 1, 100, 1, 1, 1, 1.])
    planner = ServiceFirstPlanner(graph, pairs, cfg, service_tolerance=0)
    decision = planner.decide(forecast, ci, 0, forecast)
    served = progressive_fill(np.array([8., 8.]), graph.incidence(list(decision.routes)), graph.capacities)
    assert served.sum() == 16
    assert decision.routes[0] == (0, 1, 3)


def test_service_first_replay_does_not_see_target_bin():
    cfg = config()
    cfg.update(lookback=2, delay_stretch=10)
    times = np.datetime64("2005-01-01T00:00") + np.arange(6) * np.timedelta64(15, "m")
    rates = np.zeros((6, 8, 8))
    rates[:, 0, 3] = 3
    mask = np.zeros((8, 8))
    mask[0, 3] = 1
    data = Prepared(times, rates, mask, np.ones((8, 8)), network(), [(0, 3)], {})
    carbon = np.tile([1, 500, 1, 100, 1, 1, 1, 1.], (4, 1))
    predictor = Persistence(3, mask)
    first = replay(data, cfg, rates, carbon, 2, 6, "service_first_persistence", predictor)
    altered = rates.copy()
    altered[2:, 0, 3] = 100
    second = replay(data, cfg, altered, carbon, 2, 6, "service_first_persistence", predictor)
    assert first.records[0]["routes"] == second.records[0]["routes"]
    assert first.records[0]["observed_through"] < first.records[0]["traffic_time"]
