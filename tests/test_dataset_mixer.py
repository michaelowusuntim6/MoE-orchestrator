"""Tests for the deterministic exhaustive dataset mixer."""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_dataset  # noqa: E402
from orchestrator.dataset_mixer import smart_mix, smart_mix_report  # noqa: E402


def test_ratio_computation():
    plan = smart_mix_report(["big", "small"],
                            sizes={"big": 435000, "small": 100000})
    assert [name for name, _ in plan["sorted"]] == ["big", "small"]
    assert plan["smallest"] == 100000
    assert plan["ratios"] == [4.35, 1.0]
    assert plan["wholes"] == [4, 1]
    assert plan["extras"] == pytest.approx([0.35, 0.0])
    assert plan["extra_counts"] == [35000, 0]
    assert plan["whole_total"] == 500000
    assert plan["extras_total"] == 35000
    assert plan["final_total"] == 535000


def test_three_way_ratio():
    plan = smart_mix_report(["a", "b", "c"],
                            sizes={"a": 243000, "b": 190000, "c": 100000})
    assert [n for n, _ in plan["sorted"]] == ["a", "b", "c"]
    assert plan["ratios"] == pytest.approx([2.43, 1.90, 1.00])
    assert plan["wholes"] == [2, 1, 1]
    assert plan["extras"] == pytest.approx([0.43, 0.90, 0.00])
    assert plan["extra_counts"] == [43000, 90000, 0]
    assert plan["extras_total_count"] == 133000
    assert plan["extras_total"] == 133000
    assert plan["whole_total"] == 400000
    assert plan["final_total"] == 533000


def test_all_records_used():
    big = make_dataset(1000, "big")
    small = make_dataset(435, "small")
    out = smart_mix(["big", "small"], verbose=False,
                    datasets_map={"big": big, "small": small})
    assert len(out) == 1435
    ids = list(out["id"])
    assert len(set(ids)) == 1435, "no record may be duplicated"
    assert set(ids) == {f"big{i}" for i in range(1000)} | {f"small{i}" for i in range(435)}


def test_determinism():
    big = make_dataset(1000, "big")
    small = make_dataset(435, "small")
    first = list(smart_mix(["big", "small"], seed=3407, verbose=False,
                           datasets_map={"big": big, "small": small})["id"])
    second = list(smart_mix(["big", "small"], seed=3407, verbose=False,
                            datasets_map={"big": big, "small": small})["id"])
    assert first == second


def test_different_seed_changes_order():
    big = make_dataset(1000, "big")
    small = make_dataset(435, "small")
    a = list(smart_mix(["big", "small"], seed=1, verbose=False,
                       datasets_map={"big": big, "small": small})["id"])
    b = list(smart_mix(["big", "small"], seed=2, verbose=False,
                       datasets_map={"big": big, "small": small})["id"])
    assert sorted(a) == sorted(b)      # same records
    assert a != b                      # different order


def test_single_dataset():
    only = make_dataset(435, "solo")
    out = smart_mix(["solo"], verbose=False, datasets_map={"solo": only})
    assert len(out) == 435
    assert list(out["id"]) == list(only["id"])


def test_whole_ratio_smallest_is_one():
    plan = smart_mix_report(["a", "b", "c", "d"],
                            sizes={"a": 900000, "b": 500000, "c": 120000, "d": 70000})
    assert plan["wholes"][-1] == 1
    assert plan["extra_counts"][-1] == 0
    assert min(plan["wholes"]) == 1


def test_edge_case_all_equal():
    plan = smart_mix_report(["a", "b", "c"],
                            sizes={"a": 5000, "b": 5000, "c": 5000})
    assert plan["ratios"] == [1.0, 1.0, 1.0]
    assert plan["wholes"] == [1, 1, 1]
    assert plan["extra_counts"] == [0, 0, 0]
    assert plan["extras_total"] == 0
    assert plan["whole_total"] == 15000
    assert plan["final_total"] == 15000

    out = smart_mix(["a", "b", "c"], verbose=False,
                    datasets_map={"a": make_dataset(50, "a"),
                                  "b": make_dataset(50, "b"),
                                  "c": make_dataset(50, "c")})
    assert len(out) == 150
    assert len(set(out["id"])) == 150


def test_empty_input_raises():
    with pytest.raises(ValueError):
        smart_mix_report([])


def test_duplicate_names_raise():
    with pytest.raises(ValueError):
        smart_mix_report(["a", "a"], sizes={"a": 10})


def test_smart_mix_rejects_unloaded_dataset():
    with pytest.raises(ValueError):
        smart_mix(["a", "b"], verbose=False, datasets_map={"a": make_dataset(10, "a")})
