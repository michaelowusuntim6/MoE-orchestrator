"""Helpers for building small synthetic datasets in tests."""
from __future__ import annotations


def make_dataset(size: int, prefix: str = "d"):
    """A dataset of `size` records with unique ids: <prefix>0..<prefix>N-1."""
    from datasets import Dataset
    return Dataset.from_dict({
        "id": [f"{prefix}{i}" for i in range(size)],
        "messages": [[{"role": "user", "content": f"q{i}"},
                      {"role": "assistant", "content": f"a{i}"}] for i in range(size)],
    })
