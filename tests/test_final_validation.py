import numpy as np
import pandas as pd
import pytest
from test_routing import network

from carbonroute.common import config
from carbonroute.data import Prepared
from carbonroute.final_validation import SequenceForecast, capacity_data, clustered


def test_cached_forecast_rejects_a_different_observed_history():
    histories = np.arange(8.).reshape(2, 1, 2, 2)
    forecasts = np.ones((2, 3, 2, 2))
    predictor = SequenceForecast(histories, forecasts, np.zeros((3, 2, 2)))
    np.testing.assert_array_equal(predictor.predict(histories[0]), forecasts[0])
    with pytest.raises(ValueError, match="observed history"):
        predictor.predict(histories[0])


def test_capacity_regime_preserves_inputs_and_does_not_mutate_reference_graph():
    graph = network()
    rates = np.zeros((4, 8, 8))
    mask = np.ones((8, 8))
    times = np.arange(4)
    data = Prepared(times, rates, mask, mask.copy(), graph, [(0, 3)], {})
    updated, settings = capacity_data(data, config(), 4)
    assert graph.capacity_mbps == 10
    assert updated.network.capacity_mbps == 40
    assert settings["capacity_mbps"] == 40
    np.testing.assert_array_equal(updated.network.adjacency(), graph.adjacency())
    assert updated.rates is data.rates
    assert updated.scale is data.scale


def test_bootstrap_counts_days_not_training_seeds():
    rows = []
    for day, values in enumerate(([1., 3.], [5., 7.])):
        common = {"network": "unit", "capacity_factor": 1, "scenario": "normal", "window": day}
        metrics = ("forwarding_score", "served_fraction", "overload_minutes", "route_changes")
        rows.append({**common, "policy": "reactive_carbon", **dict.fromkeys(metrics, 0.)})
        for value in values:
            rows.append({**common, "policy": "gnn", **dict.fromkeys(metrics, value)})
    result = clustered(pd.DataFrame(rows))
    assert set(result.day_clusters) == {2}
    np.testing.assert_allclose(result.mean_difference, 4)
