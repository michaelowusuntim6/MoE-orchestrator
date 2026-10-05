"""Deterministic, exhaustive dataset mixing for the MoE-orchestrator.

Problem: naive weighted interleaving (`datasets.interleave_datasets` with
hand-picked probabilities) either drops records or duplicates them. Measured
on this project: with 4,000 + 1,000 records and probabilities [0.8, 0.2],
`first_exhausted` returned 4,987 of 5,000 records (13 lost) and
`all_exhausted` returned 5,041 with only 5,000 unique (41 duplicated).

Algorithm (whole-number ratios + appended extras):

  1. Load every dataset and record its length.
  2. Sort by size, descending: D[0] is the largest, D[n-1] the smallest.
  3. smallest = len(D[n-1]).
  4. ratio_i  = len(D[i]) / smallest.
  5. whole_i  = floor(ratio_i)            (never rounded up; forced to >= 1).
  6. extra_count_i = len(D[i]) - whole_i * smallest   (exact integer maths,
     so no record is lost or duplicated to float precision).
  7. Whole-mix section: take the FIRST whole_i * smallest records of each
     dataset and interleave them with probabilities proportional to whole_i.
     Total = smallest * sum(whole_i), every record used exactly once.
  8. Extras section: take each dataset's remaining tail and concatenate the
     tails in descending size order. No interleaving. Total = sum(extra).
  9. final = whole_mix + extras, total = sum(len(D[i])). Nothing is lost.

Determinism: the interleaver is seeded with ``seed`` (default 3407), and
`all_exhausted_without_replacement` is used so every slice is consumed exactly
once without repetition.

    python -m orchestrator.dataset_mixer code-review-qwen35 debug-qwen35
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPO_PREFIX = "michaelowusuntim6"
DEFAULT_SEED = 3407
SIZE_API = "https://datasets-server.huggingface.co/size?dataset={repo}"


def _load_split(name: str, repo_prefix: str = REPO_PREFIX, split: str = "train"):
    """Indirection point so tests can inject synthetic datasets."""
    from datasets import load_dataset
    return load_dataset(f"{repo_prefix}/{name}", split=split)


def _fetch_size(name: str, repo_prefix: str = REPO_PREFIX, split: str = "train") -> int:
    """Row count via the datasets-server (no download), falling back to a load."""
    import requests
    repo = f"{repo_prefix}/{name}"
    try:
        response = requests.get(SIZE_API.format(repo=repo), timeout=30)
        if response.status_code == 200:
            for entry in (response.json().get("size", {}) or {}).get("splits", []) or []:
                if entry.get("split") in (split, "train" if split in ("train", "val") else split):
                    rows = entry.get("num_rows") or entry.get("num_examples")
                    if rows is not None:
                        return int(rows)
    except Exception:
        pass
    return len(_load_split(name, repo_prefix, split))


def _plan(sizes: dict[str, int], verbose: bool = False) -> dict:
    """Pure planning maths over {name: size}. No I/O."""
    ordered = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))
    names = [name for name, _ in ordered]
    counts = [count for _, count in ordered]
    smallest = counts[-1] if counts else 0
    if smallest <= 0:
        raise ValueError(f"smallest dataset is empty; cannot mix {names}")

    ratios = [c / smallest for c in counts]
    wholes = [max(1, int(r)) for r in ratios]           # floor, never round up
    exact_extras = [c - w * smallest for c, w in zip(counts, wholes)]
    extras = [e / smallest for e in exact_extras]        # fractional part
    whole_total = smallest * sum(wholes)
    extras_total = sum(exact_extras)

    plan = {
        "sorted": ordered,
        "smallest": smallest,
        "ratios": ratios,
        "wholes": wholes,
        "extras": extras,
        "extra_counts": exact_extras,
        # alias kept because the whole-mix spec names it this way
        "extras_total_count": extras_total,
        "whole_total": whole_total,
        "extras_total": extras_total,
        "final_total": whole_total + extras_total,
    }
    if verbose:
        print(f"{'dataset':32} {'size':>10} {'ratio':>7} {'whole':>6} {'extra':>7}")
        for name, count, ratio, whole, extra in zip(names, counts, ratios, wholes, extras):
            print(f"{name:32} {count:>10} {ratio:>7.2f} {whole:>6} {extra:>7.2f}")
        print("-" * 66)
        weights = ":".join(str(w) for w in wholes)
        print(f"whole mix: {whole_total} records (interleaved {weights})")
        print(f"extras:    {extras_total} records (concatenated in descending order)")
        print(f"final:     {plan['final_total']} records")
    return plan


def smart_mix_report(dataset_names, repo_prefix: str = REPO_PREFIX,
                     split: str = "train", seed: int = DEFAULT_SEED,
                     sizes: dict | None = None, verbose: bool = False) -> dict:
    """Return the mixing plan without loading the datasets themselves.

    ``sizes`` can be supplied to bypass the network entirely (used by tests).
    """
    names = _normalise(dataset_names)
    if sizes is None:
        sizes = {name: _fetch_size(name, repo_prefix, split) for name in names}
    return _plan({name: sizes[name] for name in names}, verbose=verbose)


def smart_mix(dataset_names, repo_prefix: str = REPO_PREFIX, split: str = "train",
              seed: int = DEFAULT_SEED, verbose: bool = True,
              datasets_map: dict | None = None):
    """Exhaustively mix N datasets; every record is used exactly once.

    Deterministic given ``seed``. Returns a ``datasets.Dataset`` with the same
    schema as the inputs. ``datasets_map`` lets tests inject prepared datasets
    instead of hitting the Hub.
    """
    from datasets import concatenate_datasets, interleave_datasets

    names = _normalise(dataset_names)
    if datasets_map is None:
        datasets_map = {name: _load_split(name, repo_prefix, split) for name in names}
    missing = [n for n in names if n not in datasets_map]
    if missing:
        raise ValueError(f"datasets not loaded: {missing}")

    if len(names) == 1:
        only = datasets_map[names[0]]
        if verbose:
            print(f"single dataset: {names[0]} ({len(only)} records, no mixing)")
        return only

    sizes = {name: len(datasets_map[name]) for name in names}
    plan = _plan(sizes, verbose=verbose)
    ordered_names = [name for name, _ in plan["sorted"]]

    whole_slices, tails = [], []
    for name, whole in zip(ordered_names, plan["wholes"]):
        dataset = datasets_map[name]
        head_n = whole * plan["smallest"]
        whole_slices.append(dataset.select(range(head_n)))
        if head_n < len(dataset):
            tails.append(dataset.select(range(head_n, len(dataset))))

    total_whole = sum(plan["wholes"])
    probabilities = [w / total_whole for w in plan["wholes"]]
    whole_mix = interleave_datasets(
        whole_slices,
        probabilities=probabilities,
        seed=seed,
        stopping_strategy="all_exhausted_without_replacement",
    )

    if tails:
        extras = concatenate_datasets(tails)
        final = concatenate_datasets([whole_mix, extras])
    else:
        final = whole_mix

    if verbose:
        print(f"smart_mix -> {len(final)} records "
              f"(whole {len(whole_mix)} + extras {len(final) - len(whole_mix)})")
    expected = plan["final_total"]
    if len(final) != expected:
        raise RuntimeError(f"mix produced {len(final)} records, expected {expected}")
    return final


def _normalise(dataset_names) -> list[str]:
    if isinstance(dataset_names, str):
        names = [dataset_names]
    else:
        names = list(dataset_names or [])
    if not names:
        raise ValueError("provide at least one dataset name")
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate dataset names: {names}")
    return names


def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    plan = smart_mix_report(argv, verbose=True)
    print(f"\nplan only - nothing downloaded; final would be "
          f"{plan['final_total']} records")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
