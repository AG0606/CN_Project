import numpy as np
import torch

from carbonroute.prediction import DemandNet, calibrate_margin


def test_margin_uses_positive_residuals_and_masks_inactive_pairs():
    mask = np.zeros((8, 8))
    mask[0, 1] = 1
    actual = np.zeros((3, 1, 8, 8))
    predicted = np.zeros_like(actual)
    actual[:, 0, 0, 1] = [0, 2, 4]
    predicted[:, 0, 0, 1] = [2, 1, 1]
    margin = calibrate_margin(actual, predicted, mask, .5)
    assert margin[0, 0, 1] == 1
    assert np.count_nonzero(margin) == 1


def test_model_masks_inactive_outputs_and_backpropagates_through_graph():
    torch.manual_seed(42)
    mask = np.zeros((8, 8), dtype=np.float32)
    mask[0, 1] = 1
    model = DemandNet(np.ones((8, 8), dtype=np.float32)/8, mask, 8, 3)
    # A nonzero head permits a gradient through the spatial layer before training.
    torch.nn.init.normal_(model.head.weight, std=.1)
    x = torch.ones((2, 12, 8, 8), requires_grad=True)
    y = model(x)
    assert y.shape == (2, 3, 8, 8)
    assert torch.all(y >= 0)
    assert torch.count_nonzero(y[:, :, mask == 0]) == 0
    y.sum().backward()
    assert torch.count_nonzero(x.grad[:, :, 7]) > 0  # Neighbor affects active origin 0.
