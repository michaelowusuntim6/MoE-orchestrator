#!/usr/bin/env python3
"""Validate every published Hugging Face corpus against the training contract.

For each of the 30 datasets under michaelowusuntim6 it checks the first 200
records of the train and validation splits:

  * top level is a dict with a "messages" list of at least 2 entries
  * every message is a dict with "role" (system|user|assistant) and "content"
  * "content" is a non-empty str (the vision format uses a list of typed
    objects, which FastLanguageModel cannot consume)
  * at least one user turn and at least one assistant turn

Memory safety: samples are read with ``streaming=True`` and row counts come
from the Hugging Face datasets-server, so validating the 663k-record corpus
does not pull gigabytes into RAM. If the server is unavailable the count falls
back to a streaming pass.

    ./venv-inference/bin/python scripts/verify_hf_datasets.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DATASETS = [
    "android-qwen35", "lineageos-tree-qwen35", "lineageos-support-qwen35",
    "android-malware-qwen35", "lineageos-generated-qwen35",
    "kernel-qwen35", "linux-qwen35", "kernel-vuln-qwen35",
    "kernel-syzfix-qwen35", "kernel-vuln-full-qwen35",
    "linux-kernel-commits-qwen35", "linux-kernel-asm-qwen35",
    "linux-kernel-ioctl-qwen35", "kernel-davinci-qwen35",
    "mql5-repos-qwen35", "mql5-expanded-qwen35", "mql5-compile-benchmark",
    "forex-calendar-qwen35", "mql5-generated-qwen35",
    "python-qwen35", "cpp-qwen35", "code-review-qwen35",
    "debug-qwen35", "python-codeparrot-qwen35",
    "security-qwen35", "security-qa-qwen35", "security-expanded-qwen35",
    "agent-tool-qwen35", "reasoning-qwen35", "uncategorized-qwen35",
]
PREFIX = "michaelowusuntim6"
# "tool" is a first-class role in the Qwen3.5 chat template (it renders
# <tool_response> blocks), so agentic corpora legitimately contain it.
VALID_ROLES = {"system", "user", "assistant", "tool"}
SIZE_API = "https://datasets-server.huggingface.co/size?dataset={repo}"


def server_row_counts(repo_id: str) -> dict:
    """{'train': N, 'validation': M} from the datasets-server, or {}."""
    import requests
    try:
        response = requests.get(SIZE_API.format(repo=repo_id), timeout=30)
        if response.status_code != 200:
            return {}
        data = response.json()
    except Exception:
        return {}
    counts = {}
    for entry in (data.get("size", {}) or {}).get("splits", []) or []:
        counts[entry.get("split")] = (entry.get("num_rows")
                                      or entry.get("num_examples"))
    return counts


def stream_count(repo_id: str, split: str, limit: int = 2_000_000) -> int | None:
    from datasets import load_dataset
    try:
        stream = load_dataset(repo_id, split=split, streaming=True)
    except Exception:
        return None
    n = 0
    for _ in stream:
        n += 1
        if n >= limit:
            break
    return n


def check_record(record, violations: dict) -> None:
    if not isinstance(record, dict):
        violations["not_a_dict"] += 1
        return
    if "messages" not in record:
        violations["missing_messages"] += 1
        return
    messages = record["messages"]
    if not isinstance(messages, list):
        violations["messages_not_list"] += 1
        return
    if len(messages) < 2:
        violations["too_few_messages"] += 1
    roles = []
    for message in messages:
        if not isinstance(message, dict):
            violations["message_not_dict"] += 1
            continue
        role = message.get("role")
        if role not in VALID_ROLES:
            violations["role_invalid"] += 1
        else:
            roles.append(role)
        if "content" not in message:
            violations["missing_content"] += 1
            continue
        content = message["content"]
        if isinstance(content, list):
            violations["content_not_str"] += 1
        elif content is None:
            violations["content_none"] += 1
        elif not isinstance(content, str):
            violations["content_not_str"] += 1
        elif not content.strip():
            violations["content_empty"] += 1
    if "user" not in roles:
        violations["no_user"] += 1
    if "assistant" not in roles:
        violations["no_assistant"] += 1


def validate_split(repo_id: str, split: str, sample: int):
    """(rows|None, violations dict, error|None)."""
    from datasets import load_dataset
    violations = {key: 0 for key in (
        "not_a_dict", "missing_messages", "messages_not_list",
        "too_few_messages", "message_not_dict", "role_invalid",
        "missing_content", "content_not_str", "content_none",
        "content_empty", "no_user", "no_assistant")}
    try:
        stream = load_dataset(repo_id, split=split, streaming=True)
    except Exception as exc:
        return None, violations, f"{type(exc).__name__}: {str(exc)[:80]}"
    taken = 0
    for record in stream:
        check_record(record, violations)
        taken += 1
        if taken >= sample:
            break
    return taken, violations, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate published HF corpora")
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--dataset", action="append", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--token", default=None)
    args = parser.parse_args(argv)

    token = args.token or os.environ.get("HF_TOKEN") or None
    if token:
        os.environ["HF_TOKEN"] = token
    names = args.dataset or DEFAULT_DATASETS
    out_path = Path(args.output) if args.output else (
        PROJECT_ROOT / "datasets" / "_validation_report.json")

    results = []
    print(f"{'dataset':32} {'train':>10} {'val':>8} {'clean':>6}  violations")
    print("-" * 100)
    for name in names:
        repo_id = f"{PREFIX}/{name}"
        counts = server_row_counts(repo_id)
        entry = {"dataset": name, "repo_id": repo_id, "sampled": args.sample,
                 "train_rows": None, "val_rows": None, "violations": {},
                 "clean": False, "errors": {}}

        train_sampled, train_v, train_err = validate_split(repo_id, "train", args.sample)
        val_sampled = None
        val_v = {}
        val_err = None
        for candidate in ("validation", "val"):
            val_sampled, val_v, val_err = validate_split(repo_id, candidate, args.sample)
            if val_err is None:
                break

        entry["train_rows"] = counts.get("train") or (
            None if train_err else stream_count(repo_id, "train"))
        entry["val_rows"] = counts.get("validation") or counts.get("val")
        entry["train_sampled"] = train_sampled
        entry["val_sampled"] = val_sampled
        merged = dict(train_v)
        for key, value in (val_v or {}).items():
            merged[key] = merged.get(key, 0) + value
        entry["violations"] = {k: v for k, v in merged.items() if v}
        if train_err:
            entry["errors"]["train"] = train_err
        if val_err and val_err.startswith(("FileNotFound", "ValueError", "Builder")):
            entry["errors"]["val"] = val_err
        entry["clean"] = (not entry["violations"]) and train_sampled is not None
        results.append(entry)

        flag = "yes" if entry["clean"] else "NO"
        detail = ", ".join(f"{k}={v}" for k, v in entry["violations"].items()) or "-"
        if train_err:
            detail = f"train error: {train_err}"
        print(f"{name:32} {entry['train_rows'] if entry['train_rows'] is not None else '?':>10} "
              f"{entry['val_rows'] if entry['val_rows'] is not None else '?':>8} "
              f"{flag:>6}  {detail}")

    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "prefix": PREFIX,
        "sampled_per_split": args.sample,
        "datasets_checked": len(results),
        "datasets_clean": sum(1 for r in results if r["clean"]),
        "results": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    clean = payload["datasets_clean"]
    print("-" * 100)
    print(f"{clean}/{len(results)} datasets clean")
    print(f"report: {out_path}")
    return 0 if clean == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
