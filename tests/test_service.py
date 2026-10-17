import numpy as np

from carbonroute.service import forwarding_score, power_model_grams, progressive_fill


def test_competing_flows_share_bottleneck_and_spare_capacity_is_reused():
    # Flow A demands only 2 Mbps. B and C share the remaining 8 Mbps on link 0.
    # C alone also uses link 1, whose 3 Mbps cap freezes C, leaving 5 for B.
    incidence = np.array([[1, 1, 1], [0, 0, 1]], dtype=float)
    served = progressive_fill(np.array([2.0, 10.0, 10.0]), incidence, np.array([10.0, 3.0]))
    np.testing.assert_allclose(served, [2.0, 5.0, 3.0])


def test_zero_demand_and_zero_capacity_are_finite():
    np.testing.assert_allclose(progressive_fill(np.array([0., 5.]), np.eye(2), np.array([2., 0.])), [0, 0])


def test_many_shared_routes_never_exceed_capacity_or_offered_rate():
    rng = np.random.default_rng(7)
    for _ in range(100):
        incidence = (rng.random((8, 6)) > .5).astype(float)
        incidence[0] = 1
        offered, capacities = rng.uniform(0, 20, 6), rng.uniform(0, 20, 8)
        served = progressive_fill(offered, incidence, capacities)
        assert (served >= 0).all()
        assert (served <= offered+1e-8).all()
        assert (incidence @ served <= capacities+1e-8).all()


def test_carbon_accounting_uses_decimal_mb_and_original_duration():
    # 8 Mbps * 900s / 8 = 900 MB; two hops sum to CI=300.
    # 900 MB * 4 J/MB * 300 g/kWh / 3,600,000 J/kWh = .3 g.
    result = forwarding_score(np.array([8.]), np.array([300.]), 900, 4)
    assert result["served_mb"] == 900
    assert result["forwarding_score"] == 300
    assert result["modeled_co2_g"] == .3
    assert forwarding_score(np.zeros(1), np.ones(1))["forwarding_score"] is None


def test_idle_only_emissions_do_not_depend_on_the_route_load():
    ci = np.array([100., 200.])
    assert power_model_grams(np.zeros(2), ci, 900, 50, 0) == 3.75
    assert power_model_grams(np.array([100., 300.]), ci, 900, 50, 0) == 3.75
