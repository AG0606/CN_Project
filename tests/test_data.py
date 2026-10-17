import numpy as np
import pandas as pd
import pytest

from carbonroute.data import ISO3, CarbonTable, parse_demand, window_indices


def test_windows_cannot_cross_split_boundary_or_missing_timestamp():
    times = np.array([0, 15, 30, 45, 75, 90, 105, 120, 135, 150, 165], dtype="timedelta64[m]")
    # Each target needs two preceding and two future bins within its own split.
    assert window_indices(times, 0, 7, lookback=2, horizon=2).tolist() == [2]
    assert window_indices(times, 7, 11, lookback=2, horizon=2).tolist() == [9]


def native(value="8", unit="MBITPERSEC", granularity="15min"):
    return f"META (\n unit = {unit}\n time = 20050504-1630\n granularity = {granularity}\n)\nDEMANDS (\n d ( fr1.fr de1.de ) 1 {value} UNLIMITED\n)"


def test_dynamic_parser_preserves_direction_and_explicit_omissions():
    stamp, matrix, omitted = parse_demand(native())
    assert stamp == np.datetime64("2005-05-04T16:30")
    assert matrix[0, 1] == 8
    assert matrix[1, 0] == 0
    assert omitted == 55


@pytest.mark.parametrize("text", [native("-1"), native("nan"), native(unit="KBPS"), native(granularity="4month")])
def test_invalid_or_aggregate_source_is_rejected(text):
    with pytest.raises(ValueError):
        parse_demand(text)


def test_carbon_is_country_matched_constant_within_day_and_complete(tmp_path):
    rows = [{"ISO": code, "Country Name": code, "Timestamp": day.strftime("%Y/%m/%d"),
             "Value": 10*(i+1), "FLAG": "F" if i == 1 else "N"}
            for day in pd.date_range("2022-06-01", periods=20) for i, code in enumerate(ISO3)]
    path = tmp_path / "carbon.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    times = np.datetime64("2005-06-07T00:00")+np.arange(192)*np.timedelta64(15, "m")
    values, mapping = CarbonTable(path).pair(times, 2022)
    np.testing.assert_allclose(values[0], [10, 20, 30, 40, 50, 60, 70, 80])
    np.testing.assert_array_equal(values[0], values[95])
    assert mapping[0]["carbon_day"] == "2022-06-07"
    assert mapping[1]["carbon_day"] == "2022-06-08"
    assert mapping[0]["flags"][1] == "F"
    # Removing every Luxembourg day must fail, not substitute a neighbor or zero.
    pd.DataFrame(rows).query("ISO != 'LUX'").to_csv(path, index=False)
    with pytest.raises(ValueError, match="No complete"):
        CarbonTable(path).pair(times, 2022)
