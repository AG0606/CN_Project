import runpy
from pathlib import Path

import pandas as pd
import pytest

from carbonroute.common import save_json, sha256


@pytest.mark.parametrize("saved_score,valid", [(None, True), (0.0, False)])
def test_empty_service_carbon_is_undefined_not_a_zero_saving(tmp_path, saved_score, valid):
    verify = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/verify_tradeoff.py"))["verify"]
    (tmp_path / "runs").mkdir()
    row = {"network": "unit", "window": 0, "scenario": "normal", "policy": "reactive_carbon",
           "served_mb": 0, "forwarding_score": saved_score, "overload_minutes": 0}
    record = {"traffic_time": "2005-01-01T00:15", "observed_through": "2005-01-01T00:00",
              "offered_mbps": [0], "carbon": [100], "served_mb": 0, "carbon_weighted_mb": 0,
              "link_utilization": [0]}
    run = tmp_path / "runs/empty.json"
    save_json(run, {"summary": row, "records": [record]})
    pd.DataFrame([row]).to_csv(tmp_path / "summary.csv", index=False)
    (tmp_path / "paired_differences.csv").write_text("policy,delta\n", encoding="utf-8")
    save_json(tmp_path / "manifest.json", {
        "status": "complete", "summary_sha256": sha256(tmp_path / "summary.csv"),
        "paired_differences_sha256": sha256(tmp_path / "paired_differences.csv"),
        "networks": {"unit": {"config": {"bin_seconds": 900}}},
        "runs": [{"run_id": "empty", "file": "runs/empty.json", "sha256": sha256(run)}],
    })
    if valid:
        verify(tmp_path)
    else:
        with pytest.raises(ValueError, match="forwarding_score"):
            verify(tmp_path)
