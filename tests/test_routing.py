import numpy as np

from carbonroute.common import ROOT, config
from carbonroute.network import Network
from carbonroute.routing import Planner


def network():
    # Independent tiny square embedded in the fixed eight-node index space.
    return Network([(i, 0) for i in range(8)], [(0, 1), (1, 3), (0, 2), (2, 3)],
                   ["a", "b", "c", "d"], 10, 1, .1)


def test_flow_does_not_double_count_its_existing_reservation():
    cfg = config(ROOT / "configs/default.json")
    cfg.update(delay_stretch=10, hold_bins=0)
    planner = Planner(network(), [(0, 3)], cfg, "predictive_carbon")
    forecast = np.zeros((3, 8, 8))
    forecast[:, 0, 3] = 7
    result = planner.decide(forecast, np.ones(8), 0)
    assert result.infeasible_pairs == 0
    assert abs(result.projected_max_utilization - .7) < 1e-9


def test_two_pairs_cannot_both_reserve_the_same_clean_bottleneck():
    cfg = config()
    cfg.update(delay_stretch=10, hold_bins=0)
    planner = Planner(network(), [(0, 3), (2, 3)], cfg, "predictive_carbon")
    forecast = np.zeros((3, 8, 8))
    forecast[:, 0, 3] = 6
    forecast[:, 2, 3] = 6
    result = planner.decide(forecast, np.array([1, 500, 1, 100, 1, 1, 1, 1.]), 0)
    matrix = planner.network.incidence(list(result.routes))
    assert (matrix @ np.array([6, 6])).max() <= 8
