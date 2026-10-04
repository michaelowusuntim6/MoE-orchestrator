"""Numerical parity tests for the chunked linear cross-entropy."""
import sys
from pathlib import Path

import pytest
import torch
import torch.nn.functional as F

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.chunked_ce import (  # noqa: E402
    chunked_linear_cross_entropy,
    shifted_chunked_lm_loss,
)


def reference(hidden, weight, labels, ignore_index=-100):
    logits = hidden @ weight.t()
    return F.cross_entropy(logits, labels, ignore_index=ignore_index)


def test_loss_matches_reference_and_gradients_match():
    torch.manual_seed(0)
    n, h, v = 53, 16, 97
    hidden = torch.randn(n, h, requires_grad=True)
    weight = torch.randn(v, h)
    labels = torch.randint(0, v, (n,))
    labels[:7] = -100

    ref = reference(hidden, weight, labels)
    ref.backward()
    ref_grad = hidden.grad.clone()

    hidden2 = hidden.detach().clone().requires_grad_(True)
    got = chunked_linear_cross_entropy(hidden2, weight, labels, chunk_size=8)
    got.backward()

    assert torch.allclose(ref, got, atol=1e-6)
    assert torch.allclose(ref_grad, hidden2.grad, atol=1e-6)


def test_chunk_size_does_not_change_result():
    torch.manual_seed(1)
    hidden = torch.randn(40, 12)
    weight = torch.randn(64, 12)
    labels = torch.randint(0, 64, (40,))
    losses = [chunked_linear_cross_entropy(hidden, weight, labels, chunk_size=c)
              for c in (1, 7, 40, 1000)]
    assert all(torch.allclose(losses[0], other, atol=1e-6) for other in losses[1:])


def test_shifted_causal_lm_loss_matches_reference():
    torch.manual_seed(2)
    b, s, h, v = 2, 21, 12, 48
    hidden = torch.randn(b, s, h, requires_grad=True)
    weight = torch.randn(v, h)
    labels = torch.randint(0, v, (b, s))
    labels[:, :5] = -100  # prompt masked

    ref = F.cross_entropy((hidden[:, :-1, :].reshape(-1, h) @ weight.t()),
                          labels[:, 1:].reshape(-1), ignore_index=-100)
    ref.backward()
    ref_grad = hidden.grad.clone()

    hidden2 = hidden.detach().clone().requires_grad_(True)
    got = shifted_chunked_lm_loss(hidden2, weight, labels, chunk_size=5)
    got.backward()

    assert torch.allclose(ref, got, atol=1e-6)
    assert torch.allclose(ref_grad, hidden2.grad, atol=1e-6)


def test_all_labels_ignored_is_finite():
    hidden = torch.randn(10, 8)
    weight = torch.randn(16, 8)
    labels = torch.full((10,), -100)
    loss = chunked_linear_cross_entropy(hidden, weight, labels, chunk_size=3)
    assert torch.isfinite(loss)
    assert loss.item() == 0.0


@pytest.mark.parametrize("dtype", [torch.bfloat16])
def test_bf16_forward_backward_is_finite(dtype):
    torch.manual_seed(3)
    hidden = torch.randn(24, 10, dtype=dtype, requires_grad=True)
    weight = torch.randn(32, 10, dtype=dtype)
    labels = torch.randint(0, 32, (24,))
    loss = chunked_linear_cross_entropy(hidden, weight, labels, chunk_size=6)
    loss.backward()
    assert torch.isfinite(loss)
    assert torch.isfinite(hidden.grad).all()
