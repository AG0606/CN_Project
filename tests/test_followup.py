import numpy as np
import pytest
import torch
from test_routing import network

from carbonroute import prediction
from carbonroute.common import config
from carbonroute.data import Prepared
from carbonroute.followup import frozen_protocol
from carbonroute.prediction import link_aware_loss


def test_link_loss_accounts_for_errors_accumulating_on_shared_links():
    error = torch.zeros((1, 1, 3, 3), requires_grad=True)
    correction = torch.zeros_like(error)
    correction[0, 0, 0, 2] = correction[0, 0, 1, 2] = 2
    error = error + correction
    actual = torch.zeros_like(error)
    actual[0, 0, 0, 2] = actual[0, 0, 1, 2] = 3
    mask = torch.zeros((3, 3), dtype=torch.bool)
    mask[0, 2] = mask[1, 2] = True
    value = link_aware_loss(error, actual, mask, [(0, 2), (1, 2)],
                            torch.tensor([[1., 1.]]), torch.tensor([10.]), .25)
    # OD MAE=2, shared-link absolute error=4; total=2+0.25*4.
    assert value.item() == pytest.approx(3)
    value.backward()


def test_training_can_finish_without_reading_test_windows(tmp_path, monkeypatch):
    cfg = config()
    cfg.update(lookback=2, epochs=1, hidden_size=4, batch_size=16)
    rates = np.zeros((36, 8, 8), dtype=np.float32)
    rates[:, 0, 3] = 1
    mask = np.zeros((8, 8), dtype=np.float32)
    mask[0, 3] = 1
    graph = network()
    times = np.datetime64("2005-01-01") + np.arange(36) * np.timedelta64(15, "m")
    meta = {"splits": {"train": [0, 12], "validation": [12, 24], "test": [24, 36]},
            "traffic_sha256": "unit-test", "graph": graph.metadata(), "pairs": [[0, 3]]}
    data = Prepared(times, rates, mask, np.ones((8, 8), dtype=np.float32), graph, [(0, 3)], meta)
    original = prediction.make_windows
    seen = []

    def guarded(prepared, settings, split):
        seen.append(split)
        assert split != "test", "Final test accessed during training"
        return original(prepared, settings, split)

    monkeypatch.setattr(prediction, "make_windows", guarded)
    prediction.train(tmp_path, cfg, data, tmp_path / "models", evaluate_test=False)
    assert seen == ["train", "validation"]
    assert not list((tmp_path / "models").glob("*test*"))


def test_frozen_protocol_rejects_later_changes(tmp_path):
    (tmp_path / "configs").mkdir()
    path = tmp_path / "configs/followup_protocol.json"
    path.write_text('{"seed":42}', encoding="utf-8")
    frozen_protocol(tmp_path, tmp_path / "study")
    path.write_text('{"seed":43}', encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen protocol changed"):
        frozen_protocol(tmp_path, tmp_path / "study")
