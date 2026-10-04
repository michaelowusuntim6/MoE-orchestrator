"""Chunked linear cross-entropy: never materialise the full vocab logits.

The OOM driver for Qwen3.5-0.8B training is the LM head: 248,320 vocabulary
entries produce ``seq_len * 248320`` values, so at seq=4096 in fp32 the logits
tensor alone is ~4 GB and its gradient another ~4 GB.

This module computes ``cross_entropy(hidden @ weight.T, labels)`` while only
ever holding **one chunk of logits at a time**, and it only needs the gradient
with respect to the hidden states (the LM head is frozen under LoRA, so the
weight gradient is never accumulated).

Verified numerically equal to the reference path (see tests/test_chunked_ce.py).

Note: ``torch.nn.functional.linear_cross_entropy`` exists in torch 2.14 and
offers a chunked path via ``LinearCrossEntropyOptions``, but on this CPU the
chunked kernel had not finished after >10 minutes for a single 4096-token
forward+backward, so it is unusable here. The manual implementation below
uses plain, well-optimised CPU matmuls and does finish.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


class _ChunkedLinearCrossEntropy(torch.autograd.Function):
    """Memory-bounded linear + cross-entropy (hidden-grad only)."""

    @staticmethod
    def forward(ctx, hidden, weight, labels, chunk_size, ignore_index, weight_grad_scale):
        # hidden: (N, H), weight: (V, H), labels: (N,) with ignore_index holes
        hidden = hidden.contiguous()
        weight = weight.contiguous()
        labels = labels.contiguous()
        total = torch.zeros((), dtype=torch.float32)
        valid = 0
        n = hidden.shape[0]
        for start in range(0, n, chunk_size):
            stop = min(start + chunk_size, n)
            label_chunk = labels[start:stop]
            mask = label_chunk != ignore_index
            valid += int(mask.sum())
            if not bool(mask.any()):
                continue
            logits = F.linear(hidden[start:stop], weight).float()
            total = total + F.cross_entropy(logits, label_chunk, ignore_index=ignore_index,
                                            reduction="sum")
            del logits
        ctx.save_for_backward(hidden, weight, labels)
        ctx.chunk_size = chunk_size
        ctx.ignore_index = ignore_index
        ctx.valid = max(valid, 1)
        ctx.weight_grad_scale = weight_grad_scale
        return total / ctx.valid

    @staticmethod
    def backward(ctx, grad_output):
        hidden, weight, labels = ctx.saved_tensors
        grad_hidden = torch.zeros_like(hidden)
        grad_weight = torch.zeros_like(weight) if ctx.weight_grad_scale else None
        scale = float(grad_output) / ctx.valid
        n = hidden.shape[0]
        for start in range(0, n, ctx.chunk_size):
            stop = min(start + ctx.chunk_size, n)
            label_chunk = labels[start:stop]
            mask = label_chunk != ctx.ignore_index
            if not bool(mask.any()):
                continue
            logits = F.linear(hidden[start:stop], weight).float()
            probs = torch.softmax(logits, dim=-1)
            # d(logits) = (softmax - onehot) * mask * scale
            rows = mask.nonzero(as_tuple=True)[0]
            probs[rows, label_chunk[rows]] -= 1.0
            probs[mask.logical_not()] = 0.0
            probs.mul_(scale)
            # matmul must be in the weight dtype (probs is fp32 for stability)
            probs_w = probs.to(weight.dtype)
            grad_hidden[start:stop] = (probs_w @ weight).to(grad_hidden.dtype)
            if grad_weight is not None:
                grad_weight += (probs.t() @ hidden[start:stop]).to(grad_weight.dtype) \
                    * ctx.weight_grad_scale
            del logits, probs, probs_w
        return grad_hidden, grad_weight, None, None, None, None


def chunked_linear_cross_entropy(hidden, weight, labels, chunk_size=256,
                                 ignore_index=-100, weight_grad_scale=0.0):
    """Memory-bounded equivalent of ``cross_entropy(hidden @ weight.T, labels)``.

    ``hidden`` is the flattened (tokens, hidden_size) activation, ``weight`` the
    LM-head matrix (vocab, hidden_size), ``labels`` the flattened targets.
    Returns a scalar loss (mean over non-ignored tokens).
    """
    if chunk_size is None or chunk_size <= 0:
        chunk_size = hidden.shape[0]
    return _ChunkedLinearCrossEntropy.apply(
        hidden, weight, labels, int(chunk_size), int(ignore_index), float(weight_grad_scale))


def shifted_chunked_lm_loss(hidden_states, lm_head_weight, labels, chunk_size=256,
                            ignore_index=-100):
    """Causal-LM loss: shift by one and apply the chunked linear CE.

    ``hidden_states``: (batch, seq, hidden); ``labels``: (batch, seq).
    Matches ``transformers`` semantics (predict token t+1 from position t).
    """
    shift_hidden = hidden_states[:, :-1, :].reshape(-1, hidden_states.shape[-1])
    shift_labels = labels[:, 1:].reshape(-1)
    return chunked_linear_cross_entropy(
        shift_hidden, lm_head_weight, shift_labels,
        chunk_size=chunk_size, ignore_index=ignore_index)
