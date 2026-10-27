import numpy as np
from test_routing import network

from carbonroute.common import config
from carbonroute.data import Prepared
from carbonroute.multipath import MultipathPlanner, Paths, fractional_service
from carbonroute.multipath_simulation import replay
from carbonroute.network import Network
from carbonroute.prediction import Persistence
from carbonroute.service import progressive_fill


def test_disjoint_paths_can_serve_more_than_a_single_path():
    cfg = config()
    cfg.update(delay_stretch=10)
    graph = network()
    paths = Paths(graph, [(0, 3)], cfg)
    forecast = np.zeros((3, 8, 8))
    forecast[:, 0, 3] = 30
    decision = MultipathPlanner(paths, cfg).decide(forecast, np.ones(8))
    np.testing.assert_allclose(decision.weights, [.5, .5], atol=1e-7)
    served = fractional_service(np.array([30.]), paths.effective(decision.weights), graph.capacities)
    assert abs(served[0]-20) < 1e-6
    assert progressive_fill(np.array([30.]), graph.incidence([(0, 1, 3)]), graph.capacities)[0] == 10


def test_subpaths_do_not_receive_extra_od_fairness_shares():
    effective = np.array([[1., 1.], [.5, 0], [.5, 0]])
    served = fractional_service(np.array([20., 20.]), effective, np.array([10., 10., 10.]))
    np.testing.assert_allclose(served, [5, 5])


def test_splitting_cannot_bypass_a_shared_capacity_cut():
    cfg = config()
    cfg.update(delay_stretch=10)
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]
    graph = Network([(i, 0) for i in range(8)], edges, [str(i) for i in range(5)], 10, 1, .1)
    paths = Paths(graph, [(0, 4)], cfg)
    forecast = np.zeros((3, 8, 8))
    forecast[:, 0, 4] = 30
    decision = MultipathPlanner(paths, cfg).decide(forecast, np.ones(8))
    served = fractional_service(np.array([30.]), paths.effective(decision.weights), graph.capacities)
    np.testing.assert_allclose(served, [10])


def test_one_hot_service_matches_existing_allocator():
    rng = np.random.default_rng(11)
    graph = network()
    matrix = graph.incidence([(0, 1, 3), (2, 3)])
    for _ in range(30):
        demand = rng.uniform(0, 30, 2)
        np.testing.assert_allclose(fractional_service(demand, matrix, graph.capacities),
                                   progressive_fill(demand, matrix, graph.capacities))


def test_carbon_lp_chooses_cleaner_path_when_capacity_allows_and_quantization_conserves():
    cfg = config()
    cfg.update(delay_stretch=10)
    paths = Paths(network(), [(0, 3)], cfg)
    forecast = np.zeros((3, 8, 8))
    forecast[:, 0, 3] = 4
    decision = MultipathPlanner(paths, cfg).decide(forecast, np.array([1, 500, 1, 100, 1, 1, 1, 1.]))
    assert decision.weights[1] > .999
    weights = paths.quantize(np.array([.33333, .66667]), 100)
    np.testing.assert_allclose(weights, [.33, .67])
    assert weights.sum() == 1


def test_split_decision_does_not_see_target_traffic():
    cfg = config()
    cfg.update(lookback=2, delay_stretch=10)
    times = np.datetime64("2005-01-01") + np.arange(6) * np.timedelta64(15, "m")
    rates = np.zeros((6, 8, 8))
    rates[:, 0, 3] = 12
    mask = np.zeros((8, 8))
    mask[0, 3] = 1
    data = Prepared(times, rates, mask, np.ones((8, 8)), network(), [(0, 3)], {})
    ci = np.ones((4, 8))
    predictor = Persistence(3, mask)
    first = replay(data, cfg, rates, ci, 2, 6, "multipath_carbon_persistence", predictor)
    changed = rates.copy()
    changed[2:, 0, 3] = 100
    second = replay(data, cfg, changed, ci, 2, 6, "multipath_carbon_persistence", predictor)
    np.testing.assert_allclose(first["records"][0]["path_fractions"], second["records"][0]["path_fractions"])
    assert first["records"][0]["observed_through"] < first["records"][0]["traffic_time"]
