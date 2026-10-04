#!/usr/bin/env python3
"""Survey the raw record shapes under datasets/downloaded/.

Reads only the first few records of each data file (never whole files) and
writes datasets/downloaded/_format_survey.json with, per dataset: the data
files, the union of top-level keys, an inferred schema family, and a
redacted preview.

    ./venv/bin/python scripts/survey_formats.py
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config  # noqa: E402

DATA_SUFFIXES = [
    ".jsonl.gz", ".json.gz", ".parquet.gz", ".jsonl", ".ndjson", ".json",
    ".parquet", ".arrow", ".csv", ".txt",
]
MAX_SAMPLE_RECORDS = 3
_SECRET_RE = re.compile(r"\b[A-Za-z0-9+/=_-]{40,}\b")

CHAT_KEYS = {"messages", "conversations", "conversation", "dialog", "dialogue", "chat"}
TOOL_KEYS = {"tools", "tool_calls", "functions", "function_call", "tool_call"}
PROMPT_KEYS = {"instruction", "instructions", "prompt", "prompts", "question", "questions",
               "query", "queries", "input", "request", "task", "problem", "human", "user"}
RESPONSE_KEYS = {"output", "outputs", "response", "responses", "answer", "answers",
                 "completion", "completions", "solution", "assistant", "gpt", "target",
                 "chosen", "rejected", "response_text"}
TEXT_KEYS = {"text", "content", "body", "document", "doc", "article", "passage"}
CODE_KEYS = {"code", "source", "snippet"}
LABEL_KEYS = {"label", "labels", "category", "class", "target_label", "sentiment"}


def find_data_files(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        name = path.name.lower()
        if any(name.endswith(suffix) for suffix in DATA_SUFFIXES):
            files.append(path)
    return files


def open_text(path: Path):
    if path.name.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="ignore")
    return path.open("r", encoding="utf-8", errors="ignore")


def redact(value: str) -> str:
    return _SECRET_RE.sub("<REDACTED>", value)[:200]


def sample_jsonl(path: Path, n: int) -> list:
    rows = []
    try:
        with open_text(path) as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append({"__malformed__": redact(line)})
                if len(rows) >= n:
                    break
    except Exception as exc:
        rows.append({"__error__": f"{type(exc).__name__}: {exc}"})
    return rows


def sample_json(path: Path, n: int) -> list:
    try:
        with open_text(path) as handle:
            data = json.load(handle)
    except Exception as exc:
        rows = sample_jsonl(path, n)
        return rows if rows else [{"__error__": f"{type(exc).__name__}: {exc}"}]
    if isinstance(data, list):
        return data[:n]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return value[:n]
        return [data]
    return []


def sample_parquet(path: Path, n: int) -> list:
    try:
        import pyarrow.parquet as pq
        rows = []
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=n):
            rows.extend(batch.to_pylist())
            if len(rows) >= n:
                break
        return rows[:n]
    except Exception as exc:
        return [{"__error__": f"{type(exc).__name__}: {exc}"}]


def sample_arrow(path: Path, n: int) -> list:
    try:
        import pyarrow as pa
        with pa.memory_map(str(path), "r") as source:
            reader = pa.ipc.open_file(source)
            batch = reader.get_batch(0)
            return batch.slice(0, n).to_pylist()
    except Exception as exc:
        return [{"__error__": f"{type(exc).__name__}: {exc}"}]


def sample_text(path: Path, n: int) -> list:
    rows = []
    try:
        with open_text(path) as handle:
            for line in handle:
                if line.strip():
                    rows.append({"text": line.rstrip("\n")})
                if len(rows) >= n:
                    break
    except Exception:
        pass
    return rows


def read_sample(path: Path, n: int = MAX_SAMPLE_RECORDS) -> list:
    name = path.name.lower()
    if name.endswith((".jsonl", ".jsonl.gz", ".ndjson")):
        return sample_jsonl(path, n)
    if name.endswith((".json", ".json.gz")):
        return sample_json(path, n)
    if name.endswith((".parquet", ".parquet.gz")):
        return sample_parquet(path, n)
    if name.endswith(".arrow"):
        return sample_arrow(path, n)
    if name.endswith((".csv", ".txt")):
        return sample_text(path, n)
    return []


def record_keys(rows: list) -> set[str]:
    keys = set()
    for row in rows:
        if isinstance(row, dict):
            keys |= set(row.keys())
    return keys


def infer_family(keys: set[str], preview: str) -> str:
    low = {k.lower() for k in keys}
    if low & CHAT_KEYS:
        return "chat_messages"
    if low & TOOL_KEYS:
        return "tool_calls"
    if (low & PROMPT_KEYS) and (low & RESPONSE_KEYS):
        return "instruction_response"
    if low & TEXT_KEYS and not (low & (PROMPT_KEYS | RESPONSE_KEYS)):
        return "text_only"
    if low & CODE_KEYS and not (low & PROMPT_KEYS):
        return "code_only"
    if low & LABEL_KEYS:
        return "classification"
    if low & PROMPT_KEYS:
        return "instruction_response"
    return "unknown"


def first_preview(rows: list) -> str:
    for row in rows:
        if isinstance(row, dict):
            for key in ("messages", "conversations", "instruction", "prompt", "question",
                        "query", "text", "content", "code", "output", "response", "answer"):
                if key in row:
                    return redact(json.dumps(row[key], ensure_ascii=False)[:400])
            return redact(json.dumps(row, ensure_ascii=False)[:400])
    return ""


def survey_dataset(dataset_dir: Path) -> dict:
    files = find_data_files(dataset_dir)
    file_reports = []
    all_keys = set()
    family_votes = Counter()
    preview = ""
    for path in files:
        rows = read_sample(path)
        keys = record_keys(rows)
        family = infer_family(keys, "")
        if rows:
            family_votes[family] += 1
        all_keys |= keys
        file_reports.append({
            "file": str(path.relative_to(dataset_dir)),
            "bytes": path.stat().st_size,
            "sampled": len(rows),
            "keys": sorted(keys),
            "family": family,
        })
        if not preview:
            preview = first_preview(rows)
    family = family_votes.most_common(1)[0][0] if family_votes else "no_data"
    return {
        "dir": str(dataset_dir),
        "data_files": len(files),
        "keys": sorted(all_keys),
        "family": family,
        "family_votes": dict(family_votes),
        "preview": preview,
        "files": file_reports,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Survey dataset record shapes")
    parser.add_argument("--config", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    cfg = Config.load(Path(args.config) if args.config else PROJECT_ROOT / "config.md")
    root = cfg.path_for("Datasets", "downloaded_root",
                        cfg.get("Datasets", "download_root", "datasets/downloaded"))
    out_path = Path(args.out) if args.out else root / "_format_survey.json"

    datasets = []
    for category_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for dataset_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            report = survey_dataset(dataset_dir)
            report["category"] = category_dir.name
            report["dataset"] = dataset_dir.name.replace("__", "/", 1)
            datasets.append(report)

    family_counts = Counter(d["family"] for d in datasets)
    out_path.write_text(json.dumps({"datasets": datasets, "families": dict(family_counts)},
                                   indent=2), encoding="utf-8")

    print(f"surveyed {len(datasets)} dataset dirs -> {out_path}\n")
    print("schema family           datasets")
    print("-" * 40)
    for family, count in family_counts.most_common():
        print(f"{family:24} {count:>5}")

    per_category = defaultdict(Counter)
    for d in datasets:
        per_category[d["category"]][d["family"]] += 1
    print("\nper category:")
    for category in sorted(per_category):
        summary = ", ".join(f"{k}={v}" for k, v in per_category[category].most_common())
        print(f"  {category:24} {summary}")

    print("\nunknown / no_data datasets:")
    for d in datasets:
        if d["family"] in ("unknown", "no_data"):
            print(f"  {d['dataset']:60} family={d['family']} keys={d['keys']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
