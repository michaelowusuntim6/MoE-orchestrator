#!/usr/bin/env python3
"""Format downloaded datasets into canonical Qwen3.5 chat records.

Canonical record (what training/finetune.py consumes, no transformation):

    {"messages": [{"role": "user", "content": "..."},
                  {"role": "assistant", "content": "..."}]}

The model's own chat template is the single source of truth: this script
never inserts <|im_start|>/<|im_end|>/<think> tokens into content. It only
produces messages; the template adds the tokens at tokenize time.

Output: datasets/formatted/<category>/{train,val}.jsonl + manifest.json

    ./venv-inference/bin/python datasets/scripts/format_for_training.py --dry-run
    ./venv-inference/bin/python datasets/scripts/format_for_training.py --category python
    ./venv-inference/bin/python datasets/scripts/format_for_training.py --verify-template
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.chat_template import render, template_kwargs, tokenize_chat  # noqa: E402
from orchestrator.config import Config  # noqa: E402

FORMATTER_VERSION = "qwen35-chat-v1"
REJECT_REASONS = ("too_short", "too_long", "empty", "missing_field", "malformed_json",
                  "unsupported_schema", "duplicate", "template_mismatch")

# Datasets we deliberately do not format (retrieval corpora, raw text,
# classification, load-test graphs). Documented in docs/DATA_PIPELINE.md.
EXCLUDED_DATASETS = {
    "mteb/cqadupstack-android": "retrieval corpus (no prompts)",
    "GreenNode/cqadupstack-android-vn": "retrieval corpus (no prompts)",
    "CoIR-Retrieval/codefeedback-mt-queries-corpus": "query corpus (no answers)",
    "CoIR-Retrieval/codefeedback-st-queries-corpus": "query corpus (no answers)",
    "kirill-vas/swebench_verified_prompts_v1": "prompts only (no responses)",
    "dumb-dev/cpp-10k": "raw code corpus (exclusion candidate from audit)",
    "b-mc2/cli-commands-explained": "code-only records (no instruction)",
    "rogue-security/coding-agent-security-benchmark": "classification only",
    "ruchit11111/coding-agent-security-benchmark": "classification only",
    "tomhodemon/grounded-visual-spatial-reasoning": "visual grounding classifier",
    "zetomatoz/guidellm-agentic-coding-trajectories": "load-test trajectory graph",
    "sg-c/aws_bedrock_documentation_demo": "doc chunks + tiny QA subset (<500)",
    "mhardalov/reasoning_bg": "no data files downloaded",
    "seablue/DiDi_GAIA_dataset_jsonl": "no data files downloaded",
}

# Datasets needing a file-level (not record-level) adapter.
FILE_MODE = {
    "mondk/agentic-coding-traces": "claude_session",
    "HydraLM/python-code-instructions-18k-alpaca-standardized": "grouped_conversation",
}

MAX_INLINE_JSON_BYTES = 256 * 1024 * 1024

DATA_SUFFIXES = (".jsonl.gz", ".json.gz", ".jsonl", ".ndjson", ".json", ".parquet", ".csv")

PROMPT_ALIASES = ("instruction", "instructions", "prompt", "question", "query", "input",
                  "task", "problem", "request", "human", "user", "Open-ended Verifiable Question",
                  "Question Text")
RESPONSE_ALIASES = ("output", "response", "answer", "completion", "solution", "assistant",
                    "gpt", "target", "Response", "Gold Answer", "Complex_CoT", "Reasonings",
                    "self_answer", "raw_response")
MESSAGE_KEYS = ("messages", "conversations", "conversation", "dialog", "dialogue", "chat",
                "trace", "content")


# --------------------------------------------------------------------------
# normalization helpers
# --------------------------------------------------------------------------
def normalize_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = "\n".join(normalize_text(v) for v in value)
    elif isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _role(value: str) -> str:
    value = str(value).strip().lower()
    return {"human": "user", "user": "user", "prompt": "user", "agent": "assistant",
            "assistant": "assistant", "gpt": "assistant", "bot": "assistant",
            "system": "system", "instruction": "user", "input": "user",
            "output": "assistant", "tool": "tool"}.get(value, "")


def _content_text(value) -> str:
    """Extract plain text from a string or a list of content blocks."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item and isinstance(item["text"], str):
                    parts.append(item["text"])
                elif item.get("type") == "text" and item.get("text") is not None:
                    parts.append(str(item["text"]))
        return "\n".join(parts)
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return value["text"]
    return ""


def _messages_from_list(seq) -> list[dict] | None:
    messages = []
    for item in seq:
        if not isinstance(item, dict):
            return None
        role = _role(item.get("role", item.get("from", item.get("message_type", ""))))
        if not role:
            return None
        text = normalize_text(_content_text(item.get("content", item.get("message", item.get("value", "")))))
        if text:
            messages.append({"role": role, "content": text})
    return messages or None


# --------------------------------------------------------------------------
# record adapters
# --------------------------------------------------------------------------
def messages_from_record(record) -> list[dict] | None:
    """Best-effort mapping of one raw record to canonical messages."""
    if isinstance(record, (list, tuple)) and len(record) == 2 and isinstance(record[1], dict):
        # Topical-Chat style: [id, {"content": [{"message", "agent"}, ...]}]
        content = record[1].get("content")
        if isinstance(content, list):
            messages = []
            for turn in content:
                if not isinstance(turn, dict):
                    continue
                role = _role(turn.get("agent", ""))
                text = normalize_text(_content_text(turn.get("message", "")))
                if not role:
                    role = "user" if not messages else "assistant"
                if text:
                    messages.append({"role": role, "content": text})
            return messages or None
        return None

    if not isinstance(record, dict):
        return None

    empty_messages = False
    for key in MESSAGE_KEYS:
        value = record.get(key)
        if key == "content" and not isinstance(value, list):
            continue
        if isinstance(value, list):
            if not value:
                if key in ("messages", "conversations", "conversation"):
                    empty_messages = True
                continue
            if isinstance(value[0], dict):
                messages = _messages_from_list(value)
                if messages:
                    return messages
                empty_messages = True

    # {"vars": {"question": ..., "answer": ...}}
    variables = record.get("vars")
    if isinstance(variables, dict):
        question = variables.get("question")
        answer = variables.get("answer")
        if question and answer:
            return [{"role": "user", "content": normalize_text(question)},
                    {"role": "assistant", "content": normalize_text(answer)}]

    # goal + step_instructions (AndroidControl)
    if record.get("goal") and record.get("step_instructions"):
        plan = "\n".join(f"{i + 1}. {normalize_text(s)}"
                         for i, s in enumerate(record["step_instructions"]) if normalize_text(s))
        if plan:
            return [{"role": "user", "content": normalize_text(record["goal"])},
                    {"role": "assistant", "content": plan}]

    prompt = next((record[k] for k in PROMPT_ALIASES if record.get(k)), None)
    response = next((record[k] for k in RESPONSE_ALIASES if record.get(k)), None)
    if prompt and response:
        extra = record.get("additional_instructions") or record.get("input") or ""
        user = normalize_text(prompt)
        if isinstance(extra, str) and extra.strip() and extra.strip() != user:
            user = f"{user}\n\n{normalize_text(extra)}"
        return [{"role": "user", "content": user},
                {"role": "assistant", "content": normalize_text(response)}]

    return [] if empty_messages else None


def claude_session_messages(rows: list) -> list[dict] | None:
    """mondk/agentic-coding-traces: one file = one Claude-Code session."""
    messages = []
    for row in rows:
        if not isinstance(row, dict) or row.get("type") != "message":
            continue
        message = row.get("message")
        if not isinstance(message, dict):
            continue
        role = _role(message.get("role", ""))
        text = normalize_text(_content_text(message.get("content", "")))
        if role in ("user", "assistant") and text:
            messages.append({"role": role, "content": text})
    return messages or None


def grouped_conversation_messages(rows: list) -> list[dict] | None:
    """HydraLM alpaca-standardized: rows are messages keyed by conversation_id."""
    ordered = sorted((r for r in rows if isinstance(r, dict)),
                     key=lambda r: (str(r.get("conversation_id", "")), int(r.get("message_id", 0) or 0)))
    messages = []
    for row in ordered:
        role = _role(row.get("message_type", ""))
        text = normalize_text(row.get("message", ""))
        if not role or not text:
            continue
        if messages and messages[-1]["role"] == role == "user":
            messages[-1]["content"] += "\n\n" + text
        else:
            messages.append({"role": role, "content": text})
    return messages or None


# --------------------------------------------------------------------------
# file readers (streaming)
# --------------------------------------------------------------------------
def open_text(path: Path):
    if path.name.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="ignore")
    return path.open("r", encoding="utf-8", errors="ignore")


def iter_records(path: Path):
    """Yield raw records from a file. Raises RuntimeError if unstreamable."""
    name = path.name.lower()
    if name.endswith((".jsonl", ".jsonl.gz", ".ndjson")):
        with open_text(path) as handle:
            for line in handle:
                if line.strip():
                    yield line
        return
    if name.endswith((".json", ".json.gz")):
        if path.stat().st_size > MAX_INLINE_JSON_BYTES:
            raise RuntimeError(f"unstreamable JSON array ({path.stat().st_size} bytes)")
        with open_text(path) as handle:
            data = json.load(handle)
        if isinstance(data, list):
            for row in data:
                yield json.dumps(row, ensure_ascii=False)
        else:
            yield json.dumps(data, ensure_ascii=False)
        return
    if name.endswith(".parquet"):
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1000):
            for row in batch.to_pylist():
                yield json.dumps(row, ensure_ascii=False)
        return
    if name.endswith(".csv"):
        with open_text(path) as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield json.dumps(row, ensure_ascii=False)
        return
    raise RuntimeError(f"unsupported file type: {path.name}")


def read_all(path: Path, limit: int = 200_000) -> list:
    rows = []
    for raw in iter_records(path):
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            rows.append({"__malformed__": raw[:200]})
        if len(rows) >= limit:
            break
    return rows


def data_files(dataset_dir: Path) -> list[Path]:
    files = []
    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        if any(path.name.lower().endswith(s) for s in DATA_SUFFIXES):
            files.append(path)
    return files


# --------------------------------------------------------------------------
# dedup + validation
# --------------------------------------------------------------------------
def dedup_key(messages: list[dict], seed: int) -> bytes:
    """Exact-match dedup over the whole record (seed-namespaced).

    A prefix-only key (system + first 64 user chars + first 128 assistant
    chars) collapsed 4,980 distinct kernel records that share an instruction
    header, so the full normalized record is hashed instead. Memory cost is
    identical: only the 16-byte digest is retained.
    """
    payload = json.dumps({"seed": seed, "messages": messages},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).digest()


def validate(messages: list[dict], min_chars: int, max_chars: int) -> tuple[dict | None, str | None]:
    cleaned = []
    for msg in messages:
        role = msg.get("role")
        content = normalize_text(msg.get("content", ""))
        if role not in {"system", "user", "assistant", "tool"}:
            return None, "unsupported_schema"
        if content:
            cleaned.append({"role": role, "content": content})
    if not cleaned:
        return None, "empty"
    if cleaned[0]["role"] == "system":
        body = cleaned[1:]
    else:
        body = cleaned
    if not any(m["role"] == "user" for m in body) or not any(m["role"] == "assistant" for m in body):
        return None, "missing_field"
    total = sum(len(m["content"]) for m in cleaned)
    if total < min_chars:
        return None, "too_short"
    if max_chars and total > max_chars:
        return None, "too_long"
    return {"messages": cleaned}, None


# --------------------------------------------------------------------------
# per-dataset formatting
# --------------------------------------------------------------------------
def format_dataset(args_dict: dict) -> dict:
    dataset_id = args_dict["dataset_id"]
    category = args_dict["category"]
    dataset_dir = Path(args_dict["dir"])
    min_chars = args_dict["min_chars"]
    max_chars = args_dict["max_chars"]
    dedup = args_dict["dedup"]
    seed = args_dict["seed"]
    max_records = args_dict["max_records"]

    result = {
        "dataset": dataset_id, "category": category, "raw": 0, "accepted": 0,
        "rejects": {r: 0 for r in REJECT_REASONS}, "files": 0, "error": None,
        "skipped_unstreamable": 0, "temp": None,
    }
    if dataset_id in EXCLUDED_DATASETS:
        result["error"] = f"excluded: {EXCLUDED_DATASETS[dataset_id]}"
        return result

    mode = FILE_MODE.get(dataset_id, "record")
    seen: set[bytes] = set()
    temp_path = Path(args_dict["temp"])
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    accepted = 0

    if args_dict.get("files"):
        files = [Path(f) for f in args_dict["files"]]
    else:
        files = data_files(dataset_dir)
    if not files:
        result["error"] = "excluded: no data files"
        return result

    with temp_path.open("w", encoding="utf-8") as out:
        for path in files:
            result["files"] += 1
            try:
                if mode == "record":
                    iterator = iter_records(path)
                else:
                    iterator = [json.dumps(r, ensure_ascii=False) for r in read_all(path)]
            except RuntimeError as exc:
                result["skipped_unstreamable"] += 1
                result.setdefault("notes", []).append(f"{path.name}: {exc}")
                continue
            except Exception as exc:  # pragma: no cover
                result["notes"] = result.get("notes", []) + [f"{path.name}: {type(exc).__name__}"]
                continue

            try:
                if mode == "record":
                    for raw in iterator:
                        result["raw"] += 1
                        record, reject = _adapt_raw(raw, mode)
                        if reject:
                            result["rejects"][reject] += 1
                            continue
                        if _emit(record, out, result, seen, dedup, min_chars, max_chars, seed):
                            accepted += 1
                        if max_records and accepted >= max_records:
                            break
                else:
                    rows = read_all(path)
                    result["raw"] += 1
                    messages = (claude_session_messages(rows) if mode == "claude_session"
                                else grouped_conversation_messages(rows))
                    if not messages:
                        result["rejects"]["unsupported_schema"] += 1
                    elif _emit(messages, out, result, seen, dedup, min_chars, max_chars, seed):
                        accepted += 1
            except Exception as exc:  # pragma: no cover
                result["notes"] = result.get("notes", []) + [f"{path.name}: {type(exc).__name__}: {exc}"]
            if max_records and accepted >= max_records:
                break

    result["accepted"] = accepted
    result["temp"] = str(temp_path)
    return result


def _adapt_raw(raw: str, mode: str):
    try:
        record = json.loads(raw)
    except json.JSONDecodeError:
        return None, "malformed_json"
    if isinstance(record, dict) and ("__malformed__" in record or "__error__" in record):
        return None, "malformed_json"
    messages = messages_from_record(record)
    if messages is None:
        return None, "unsupported_schema"
    return messages, None


def _emit(messages, out, result, seen, dedup, min_chars, max_chars, seed) -> bool:
    canonical, reject = validate(messages, min_chars, max_chars)
    if reject:
        result["rejects"][reject] += 1
        return False
    if dedup:
        key = dedup_key(canonical["messages"], seed)
        if key in seen:
            result["rejects"]["duplicate"] += 1
            return False
        seen.add(key)
    out.write(json.dumps(canonical, ensure_ascii=False) + "\n")
    return True


# --------------------------------------------------------------------------
# category driver
# --------------------------------------------------------------------------
def load_survey(root: Path) -> dict:
    path = root / "_format_survey.json"
    if not path.is_file():
        raise SystemExit(f"error: {path} missing — run scripts/survey_formats.py first")
    survey = json.loads(path.read_text(encoding="utf-8"))
    return {d["dataset"]: d for d in survey["datasets"]}


def dataset_dirs(root: Path) -> list[tuple[str, str, Path, list | None]]:
    out = []
    for category_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for dataset_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            out.append((category_dir.name, dataset_dir.name.replace("__", "/", 1), dataset_dir, None))
    return out


def split_assign(digest: bytes, val_fraction: float) -> bool:
    """Deterministic val decision from the dedup digest (order independent)."""
    if val_fraction <= 0:
        return False
    threshold = int(val_fraction * 1_000_000)
    return int.from_bytes(digest[:8], "big") % 1_000_000 < threshold


def format_category(category: str, entries, formatted_root: Path, args, tmp_root: Path) -> dict:
    started = time.time()
    tasks = [{
        "dataset_id": dataset_id, "category": category, "dir": str(directory),
        "files": [str(f) for f in files] if files else None,
        "temp": str(tmp_root / f"{category}__{dataset_id.replace('/', '__')}.jsonl"),
        "min_chars": args.min_chars, "max_chars": args.max_chars, "dedup": args.dedup,
        "seed": args.seed, "max_records": args.max_records,
    } for _, dataset_id, directory, files in entries]

    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(format_dataset, tasks))
    else:
        results = [format_dataset(task) for task in tasks]

    out_dir = formatted_root / category
    out_dir.mkdir(parents=True, exist_ok=True)
    train_path, val_path = out_dir / "train.jsonl", out_dir / "val.jsonl"

    seen: set[bytes] = set()
    counts = {"train": 0, "val": 0}
    longest, shortest = [], []
    train_hash = hashlib.sha256()
    val_hash = hashlib.sha256()
    total_rejects = {r: 0 for r in REJECT_REASONS}
    per_dataset = []

    with train_path.open("wb") as train_f, val_path.open("wb") as val_f:
        for result in results:
            for reason, count in result["rejects"].items():
                total_rejects[reason] += count
            per_dataset.append({
                "dataset": result["dataset"], "raw": result["raw"],
                "accepted": result["accepted"], "rejects": result["rejects"],
                "files": result["files"], "skipped_unstreamable": result["skipped_unstreamable"],
                "error": result["error"], "notes": result.get("notes", []),
            })
            if not result["temp"] or result["accepted"] == 0:
                continue
            with Path(result["temp"]).open("r", encoding="utf-8") as handle:
                for line in handle:
                    record = json.loads(line)
                    key = dedup_key(record["messages"], args.seed)
                    if key in seen:
                        total_rejects["duplicate"] += 1
                        per_dataset[-1]["rejects"]["duplicate"] += 1
                        continue
                    seen.add(key)
                    length = sum(len(m["content"]) for m in record["messages"])
                    payload = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
                    if split_assign(key, args.val_fraction):
                        val_f.write(payload)
                        val_hash.update(payload)
                        counts["val"] += 1
                    else:
                        train_f.write(payload)
                        train_hash.update(payload)
                        counts["train"] += 1
                    if length > 0:
                        longest.append((length, result["dataset"]))
                        shortest.append((length, result["dataset"]))

    longest = sorted(longest, reverse=True)[:20]
    shortest = sorted(shortest)[:20]

    manifest = {
        "category": category,
        "formatter_version": FORMATTER_VERSION,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "chat_template_source": "models/Qwen3.5-0.8B/tokenizer_config.json#chat_template",
        "enable_thinking": args.enable_thinking,
        "seed": args.seed,
        "val_fraction": args.val_fraction,
        "dedup": args.dedup,
        "min_chars": args.min_chars,
        "max_chars": args.max_chars,
        "source_dataset_ids": [r["dataset"] for r in results],
        "train_lines": counts["train"],
        "val_lines": counts["val"],
        "rejects": total_rejects,
        "per_dataset": per_dataset,
        "train_sha256": train_hash.hexdigest(),
        "val_sha256": val_hash.hexdigest(),
        "longest_records": [{"chars": c, "dataset": d} for c, d in longest],
        "shortest_records": [{"chars": c, "dataset": d} for c, d in shortest],
        "seconds": round(time.time() - started, 1),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------
# verification / sampling
# --------------------------------------------------------------------------
def verify_template(formatted_root: Path, categories, max_length: int, kwargs) -> int:
    from orchestrator.chat_template import assistant_span_mask
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        str(PROJECT_ROOT / "models" / "Qwen3.5-0.8B"), trust_remote_code=True)
    failures = 0
    for category in categories:
        path = formatted_root / category / "train.jsonl"
        if not path.is_file():
            print(f"{category:24} MISSING train.jsonl")
            failures += 1
            continue
        checked = 0
        problems_for_category = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                text = render(tokenizer, record["messages"], **kwargs)
                ids = tokenizer(text, add_special_tokens=False)["input_ids"]
                problems = []
                if ids[0] != 248045:
                    problems.append("does not start with <|im_start|>")
                if ids.count(248045) != text.count("<|im_start|>"):
                    problems.append("im_start token count mismatch")
                if "<|im_start|>" in "".join(m["content"] for m in record["messages"]):
                    problems.append("content contains <|im_start|>")
                if "<|im_end|>" in "".join(m["content"] for m in record["messages"]):
                    problems.append("content contains <|im_end|>")
                # Template correctness is checked on the UNtruncated render;
                # truncation is a max_length concern, not a template bug.
                _full_ids, full_mask = assistant_span_mask(tokenizer, record["messages"], **kwargs)
                if sum(full_mask) == 0:
                    problems.append("no assistant tokens in template render")
                if problems:
                    failures += 1
                    problems_for_category = problems
                    print(f"{category:24} FAIL {problems} :: {line[:160]}")
                    break
                checked += 1
                if checked >= 3:
                    break
        if checked and not problems_for_category:
            print(f"{category:24} PASS ({checked} records checked)")
    return 1 if failures else 0


def sample(categories, formatted_root: Path, n: int) -> None:
    for category in categories:
        path = formatted_root / category / "train.jsonl"
        if not path.is_file():
            continue
        print(f"\n===== {category} =====")
        with path.open("r", encoding="utf-8") as handle:
            for i, line in enumerate(handle):
                if i >= n:
                    break
                print(json.dumps(json.loads(line), ensure_ascii=False, indent=2)[:1200])


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="format_for_training.py",
        description="Format downloaded datasets into Qwen3.5 chat records.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--category", action="append", default=None)
    parser.add_argument("--dataset", action="append", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--min-chars", type=int, default=None)
    parser.add_argument("--max-chars", type=int, default=None)
    parser.add_argument("--val-fraction", type=float, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dedup", dest="dedup", action="store_true", default=None)
    parser.add_argument("--no-dedup", dest="dedup", action="store_false")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--report", default=None)
    parser.add_argument("--enable-thinking", dest="enable_thinking", action="store_true", default=None)
    parser.add_argument("--template-kwargs", default=None)
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--verify-template", action="store_true")
    parser.add_argument("--no-generated", action="store_true",
                        help="Skip the datasets/generated/*.jsonl files")
    parser.add_argument("--rebuild-report", action="store_true",
                        help="Rebuild _report.json from every <category>/manifest.json")
    return parser.parse_args(argv)


def rebuild_report(formatted_root: Path) -> int:
    """Aggregate every <category>/manifest.json into _report.json."""
    report = {"formatter_version": FORMATTER_VERSION,
              "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
              "categories": {}, "chat_template_source":
              "models/Qwen3.5-0.8B/tokenizer_config.json#chat_template"}
    for manifest_path in sorted(formatted_root.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report["categories"][manifest["category"]] = manifest
    out = formatted_root / "_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    tot = {"train": 0, "val": 0, "dup": 0, "rej": 0}
    print(f"{'category':22} {'train':>9} {'val':>7} {'accepted':>9} {'dupes':>7} {'rejected':>9}")
    for cat, m in sorted(report["categories"].items()):
        dup = m["rejects"]["duplicate"]
        rej = sum(v for k, v in m["rejects"].items() if k != "duplicate")
        tot["train"] += m["train_lines"]; tot["val"] += m["val_lines"]
        tot["dup"] += dup; tot["rej"] += rej
        print(f"{cat:22} {m['train_lines']:>9} {m['val_lines']:>7} "
              f"{m['train_lines'] + m['val_lines']:>9} {dup:>7} {rej:>9}")
    print(f"{'TOTAL':22} {tot['train']:>9} {tot['val']:>7} "
          f"{tot['train'] + tot['val']:>9} {tot['dup']:>7} {tot['rej']:>9}")
    print(f"report: {out}")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = Config.load(Path(args.config) if args.config else PROJECT_ROOT / "config.md")
    section = "Formatted_datasets"

    root = cfg.path_for("Datasets", "downloaded_root",
                        cfg.get("Datasets", "download_root", "datasets/downloaded"))
    formatted_root = Path(args.output_dir) if args.output_dir else cfg.path_for(
        section, "formatted_root", "datasets/formatted")
    args.min_chars = args.min_chars if args.min_chars is not None else cfg.get_int(section, "min_chars", 32)
    args.max_chars = args.max_chars if args.max_chars is not None else cfg.get_int(section, "max_chars", 64000)
    args.val_fraction = (args.val_fraction if args.val_fraction is not None
                         else cfg.get_float(section, "val_fraction", 0.02))
    args.seed = args.seed if args.seed is not None else cfg.get_int(section, "seed", 42)
    args.dedup = cfg.get_bool(section, "dedup", True) if args.dedup is None else args.dedup
    if args.enable_thinking is None:
        args.enable_thinking = cfg.get_bool(section, "enable_thinking", False)
    extra = json.loads(args.template_kwargs) if args.template_kwargs else None
    kwargs = template_kwargs(args.enable_thinking, extra)

    entries = dataset_dirs(root)
    # --verify-template / --sample operate on what is already formatted, so
    # they must not depend on the download root (public corpora live outside it).
    if args.verify_template or args.sample:
        cats = list(args.category) if args.category else sorted(
            p.name for p in formatted_root.iterdir() if p.is_dir())
        if args.verify_template:
            return verify_template(formatted_root, cats,
                                   cfg.get_int("Training", "max_length", 128), kwargs)
        sample(cats, formatted_root, args.sample)
        return 0

    if not args.no_generated:
        for name, key in (("generated_lineageos", "generated_lineageos"),
                          ("generated_mql5", "generated_mql5")):
            path = cfg.path_for("Datasets", key, "")
            if path.is_file():
                entries.append((name, f"local/{key}", path.parent, [path]))
    if args.category:
        entries = [e for e in entries if e[0] in set(args.category)]
    if args.dataset:
        wanted = {d.replace("__", "/") for d in args.dataset}
        entries = [e for e in entries if e[1] in wanted or e[1].replace("/", "__") in args.dataset]

    categories = sorted({e[0] for e in entries})
    if not categories:
        raise SystemExit("error: no datasets matched the given --category/--dataset")

    if args.dry_run:
        print(f"dry run: {len(entries)} datasets across {len(categories)} categories")
        for category in categories:
            subset = [e for e in entries if e[0] == category]
            excluded = sum(1 for _, did, _, _files in subset if did in EXCLUDED_DATASETS)
            print(f"  {category:24} datasets={len(subset):3} excluded={excluded}")
        print(f"would write: {formatted_root}/<category>/{{train,val}}.jsonl")
        return 0

    if args.rebuild_report:
        return rebuild_report(formatted_root)

    tmp_root = formatted_root / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report) if args.report else formatted_root / "_report.json"
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report.setdefault("categories", {})
        except json.JSONDecodeError:
            report = {}
    else:
        report = {}
    report["formatter_version"] = FORMATTER_VERSION
    report["generated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    report["chat_template_source"] = "models/Qwen3.5-0.8B/tokenizer_config.json#chat_template"
    failures = []

    for i, category in enumerate(categories, 1):
        subset = [e for e in entries if e[0] == category]
        manifest = format_category(category, subset, formatted_root, args, tmp_root)
        report["categories"][category] = manifest
        status = "ok" if manifest["train_lines"] > 0 else "EMPTY"
        print(f"progress: {i}/{len(categories)}  {category}  "
              f"{manifest['train_lines']}/{manifest['train_lines'] + manifest['val_lines']}  {status}")
        if manifest["train_lines"] == 0:
            failures.append(category)

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport: {report_path}")
    if failures:
        print(f"categories with no training rows: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
