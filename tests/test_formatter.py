"""Tests for the Qwen3.5 data pipeline (formatter + finetune contract)."""
import importlib.util
import json
import sys
import tracemalloc
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.chat_template import render, template_kwargs, tokenize_chat  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fmt():
    return _load(PROJECT_ROOT / "datasets" / "scripts" / "format_for_training.py", "fmt")


@pytest.fixture(scope="module")
def finetune():
    return _load(PROJECT_ROOT / "training" / "finetune.py", "finetune")


@pytest.fixture(scope="module")
def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(
        str(PROJECT_ROOT / "models" / "Qwen3.5-0.8B"), trust_remote_code=True)


def make_args(fmt, **overrides):
    args = fmt.parse_args([])
    args.min_chars = overrides.get("min_chars", 4)
    args.max_chars = overrides.get("max_chars", 100000)
    args.val_fraction = overrides.get("val_fraction", 0.0)
    args.seed = overrides.get("seed", 42)
    args.dedup = overrides.get("dedup", True)
    args.max_records = overrides.get("max_records", None)
    args.workers = 1
    args.enable_thinking = False
    return args


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


# -- finetune contract ------------------------------------------------------
def test_canonical_schema_matches_finetune_contract(finetune, tmp_path):
    record = {"messages": [{"role": "user", "content": "hi"},
                           {"role": "assistant", "content": "hello"}]}
    assert finetune.record_to_messages(record) == record["messages"]
    path = tmp_path / "train.jsonl"
    write_jsonl(path, [record])
    assert finetune.load_examples(path) == [{"messages": record["messages"]}]


def test_finetune_rejects_unknown_shape(finetune):
    assert finetune.record_to_messages({"foo": 1}) is None


def test_jsonl_lines_are_valid_json(fmt, tmp_path):
    dataset_dir = tmp_path / "dl" / "cat" / "owner__name"
    write_jsonl(dataset_dir / "data.jsonl", [
        {"messages": [{"role": "user", "content": "a" * 20},
                      {"role": "assistant", "content": "b" * 20}]},
    ])
    args = make_args(fmt)
    entries = [("cat", "owner/name", dataset_dir, None)]
    manifest = fmt.format_category("cat", entries, tmp_path / "out", args, tmp_path / "tmp")
    assert manifest["train_lines"] == 1
    for line in (tmp_path / "out" / "cat" / "train.jsonl").read_text().splitlines():
        json.loads(line)


def test_dedup_removes_exact_duplicates(fmt, tmp_path):
    record = {"messages": [{"role": "user", "content": "same question here"},
                           {"role": "assistant", "content": "same answer here"}]}
    dataset_dir = tmp_path / "dl" / "cat" / "owner__name"
    write_jsonl(dataset_dir / "data.jsonl", [record, record, record])
    args = make_args(fmt)
    task = {
        "dataset_id": "owner/name", "category": "cat", "dir": str(dataset_dir),
        "temp": str(tmp_path / "t.jsonl"), "min_chars": 4, "max_chars": 100000,
        "dedup": True, "seed": 42, "max_records": None,
    }
    result = fmt.format_dataset(task)
    assert result["raw"] == 3
    assert result["accepted"] == 1
    assert result["rejects"]["duplicate"] == 2


def test_reject_reasons_are_counted(fmt, tmp_path):
    rows = [
        {"messages": [{"role": "user", "content": "hi"},
                      {"role": "assistant", "content": "ok"}]},          # too_short
        {"foo": "bar"},                                                   # unsupported_schema
        {"messages": [{"role": "user", "content": "only a user turn"}]},  # missing_field
        {"messages": []},                                                 # empty
    ]
    dataset_dir = tmp_path / "dl" / "cat" / "owner__name"
    write_jsonl(dataset_dir / "data.jsonl", rows)
    # add a malformed line
    with (dataset_dir / "data.jsonl").open("a") as handle:
        handle.write("{not json}\n")
    task = {
        "dataset_id": "owner/name", "category": "cat", "dir": str(dataset_dir),
        "temp": str(tmp_path / "t.jsonl"), "min_chars": 50, "max_chars": 100000,
        "dedup": True, "seed": 42, "max_records": None,
    }
    result = fmt.format_dataset(task)
    assert result["rejects"]["too_short"] == 1
    assert result["rejects"]["unsupported_schema"] == 1
    assert result["rejects"]["missing_field"] == 1
    assert result["rejects"]["empty"] == 1
    assert result["rejects"]["malformed_json"] == 1
    assert result["accepted"] == 0


def test_seed_determinism(fmt, tmp_path):
    rows = [{"messages": [{"role": "user", "content": f"question number {i}"},
                          {"role": "assistant", "content": f"answer number {i} " + "x" * 40}]}
            for i in range(200)]
    dataset_dir = tmp_path / "dl" / "cat" / "owner__name"
    write_jsonl(dataset_dir / "data.jsonl", rows)

    def run(out):
        args = make_args(fmt, val_fraction=0.05, seed=42, min_chars=4)
        entries = [("cat", "owner/name", dataset_dir, None)]
        fmt.format_category("cat", entries, out, args, out / ".tmp")
        return (out / "cat" / "train.jsonl").read_bytes(), (out / "cat" / "val.jsonl").read_bytes()

    train_a, val_a = run(tmp_path / "outA")
    train_b, val_b = run(tmp_path / "outB")
    assert train_a == train_b
    assert val_a == val_b
    assert len(train_a) > 0 and len(val_a) > 0


def test_streaming_on_large_jsonl(fmt, tmp_path):
    dataset_dir = tmp_path / "dl" / "cat" / "owner__big"
    path = dataset_dir / "data.jsonl"
    dataset_dir.mkdir(parents=True)
    with path.open("w", encoding="utf-8") as handle:
        for i in range(100_000):
            handle.write(json.dumps({"messages": [
                {"role": "user", "content": f"q{i} " + "a" * 30},
                {"role": "assistant", "content": f"answer {i} " + "b" * 30}]}) + "\n")
    task = {
        "dataset_id": "owner/big", "category": "cat", "dir": str(dataset_dir),
        "temp": str(tmp_path / "big.jsonl"), "min_chars": 4, "max_chars": 100000,
        "dedup": True, "seed": 42, "max_records": None,
    }
    tracemalloc.start()
    result = fmt.format_dataset(task)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert result["accepted"] == 100_000
    assert peak < 200 * 1024 * 1024, f"peak {peak/1e6:.1f} MB"


# -- chat template guarantees ----------------------------------------------
def test_chat_template_roundtrip(fmt, tokenizer):
    record = {"messages": [{"role": "user", "content": "What is the capital of France?"},
                           {"role": "assistant", "content": "Paris."}]}
    kwargs = template_kwargs(False)
    text = render(tokenizer, record["messages"], **kwargs)
    ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    assert ids[0] == 248045, "must start with <|im_start|>"
    assert text.count("<|im_start|>") == 2
    content = "".join(m["content"] for m in record["messages"])
    assert "<|im_start|>" not in content and "<|im_end|>" not in content
    enc = tokenize_chat(tokenizer, record["messages"], 128, **kwargs)
    assert enc["assistant_tokens"] > 0
    assert any(label == -100 for label in enc["labels"])


def _transformers_major() -> int:
    import transformers
    return int(str(transformers.__version__).split(".")[0])


def test_enable_thinking_flag_changes_template(tokenizer):
    if _transformers_major() < 5:
        pytest.skip("transformers <5 does not forward enable_thinking to the "
                    "chat template (see docs/QWEN_CHAT_TEMPLATE.md mismatch #6); "
                    "training runs on venv-inference (transformers 5.x)")
    msgs = [{"role": "user", "content": "hi"}]
    on = render(tokenizer, msgs, add_generation_prompt=True, **template_kwargs(True))
    off = render(tokenizer, msgs, add_generation_prompt=True, **template_kwargs(False))
    assert on != off
    assert on.endswith("<think>\n")
    assert off.rstrip("\n").endswith("</think>")


def test_formatter_writes_no_special_tokens(fmt, tmp_path):
    dataset_dir = tmp_path / "dl" / "cat" / "owner__name"
    write_jsonl(dataset_dir / "data.jsonl", [
        {"instruction": "How do I list files?", "output": "Use ls -la in the terminal."},
    ])
    args = make_args(fmt, min_chars=4)
    entries = [("cat", "owner/name", dataset_dir, None)]
    fmt.format_category("cat", entries, tmp_path / "out", args, tmp_path / "tmp")
    text = (tmp_path / "out" / "cat" / "train.jsonl").read_text()
    assert "<|im_start|>" not in text and "<|im_end|>" not in text
    assert json.loads(text.splitlines()[0])["messages"][0]["role"] == "user"
