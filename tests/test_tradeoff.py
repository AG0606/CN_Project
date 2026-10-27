import numpy as np
from test_routing import network

from carbonroute.common import config
from carbonroute.data import Prepared
from carbonroute.prediction import Persistence
from carbonroute.routing import CurrentBinOracle, TradeoffPlanner
from carbonroute.simulation import replay


def test_tradeoff_budget_and_causal_replay():
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
    original = replay(data, cfg, rates, carbon, 2, 6, "tradeoff_persistence", predictor)
    changed = rates.copy()
    changed[2:, 0, 3] = 100
    altered = replay(data, cfg, changed, carbon, 2, 6, "tradeoff_persistence", predictor)
    assert original.records[0]["routes"] == altered.records[0]["routes"]
    assert original.records[0]["reactive_carbon_budget"] == altered.records[0]["reactive_carbon_budget"]
    assert original.summary["carbon_budget_violations"] == 0
    assert original.records[0]["observed_through"] == "2005-01-01T00:15"


def test_oracle_prefers_low_carbon_feasible_path_and_is_explicitly_clairvoyant():
    cfg = config()
    cfg.update(lookback=2, delay_stretch=10)
    graph = network()
    carbon = np.array([1, 500, 1, 100, 1, 1, 1, 1.])
    demand = np.zeros((8, 8))
    demand[0, 3] = 3
    oracle = CurrentBinOracle(graph, [(0, 3)], cfg)
    decision = oracle.decide_actual(demand, carbon)
    candidates = graph.candidates([(0, 3)], cfg["candidate_paths"], cfg["delay_stretch"])[0]
    feasible = [r for r in candidates if (graph.incidence([r])[:, 0] * 3 / graph.capacities).max() <= 1]
    assert decision.routes[0] in feasible
    assert sum(carbon[i] for i in decision.routes[0][:-1]) == min(
        sum(carbon[i] for i in r[:-1]) for r in feasible)
    assert decision.reasons == ("oracle-actual-demand",)


def test_tradeoff_uses_reactive_reference_as_admissible_assignment():
    cfg = config()
    cfg.update(delay_stretch=10)
    graph = network()
    forecast = np.zeros((cfg["horizon"], 8, 8))
    forecast[:, 0, 3] = 5
    ci = np.array([1, 500, 1, 100, 1, 1, 1, 1.])
    decision = TradeoffPlanner(graph, [(0, 3)], cfg, budget_fraction=0).decide(
        forecast, ci, 0, forecast)
    assert decision.carbon_budget_met
    assert decision.predicted_carbon_cost <= decision.reactive_carbon_budget + 1e-9
    assert decision.projected_max_utilization <= decision.projected_peak_limit + 1e-9
    assert decision.projected_peak_limit == max(cfg["utilization_limit"], decision.projected_reference_peak)
