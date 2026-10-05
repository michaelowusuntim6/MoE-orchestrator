#!/usr/bin/env python3
"""Format the Prompt-2 public sources into Qwen3.5-native corpora.

Reuses the canonical schema, reject taxonomy, dedup key and deterministic
split from datasets/scripts/format_for_training.py, so every record produced
here is directly consumable by training/finetune.py. No <|im_start|> /
<|im_end|> is ever written into content — the chat template adds them.

    ./venv-inference/bin/python scrapers/format_public.py --list
    ./venv-inference/bin/python scrapers/format_public.py --category kernel_vuln
    ./venv-inference/bin/python scrapers/format_public.py --all
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import human_bytes, load_config  # noqa: E402

FMT_PATH = PROJECT_ROOT / "datasets" / "scripts" / "format_for_training.py"
_spec = importlib.util.spec_from_file_location("moe_formatter", FMT_PATH)
FMT = importlib.util.module_from_spec(_spec)
sys.modules["moe_formatter"] = FMT
_spec.loader.exec_module(FMT)

HF_ROOT = PROJECT_ROOT / "datasets" / "public" / "huggingface"
GH_ROOT = PROJECT_ROOT / "datasets" / "public" / "github"
LOS_ROOT = PROJECT_ROOT / "datasets" / "public" / "lineageos_tree"

SYSTEM_LINEAGEOS = "You are a LineageOS support expert."
SYSTEM_SECURITY = "You are a security expert."


# ---------------------------------------------------------------- helpers
def rec(system: str | None, user: str, assistant: str) -> dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    messages.append({"role": "assistant", "content": assistant})
    return {"messages": messages}


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def verdict_sentence(rows: list[dict]) -> str:
    passing = [r for r in rows if r.get("bucket") == "compile-pass"]
    if passing:
        r = passing[0]
        return (f"The reference implementation compiled and passed validation "
                f"(bucket=compile-pass, errors=0, ex5_exists={r.get('ex5_exists')}, "
                f"arm={r.get('arm')}).")
    r = rows[0] if rows else {}
    return (f"The reference implementation did not compile cleanly in this release "
            f"(bucket={r.get('bucket')}, errors={r.get('errors')}).")


# ---------------------------------------------------------------- adapters
def gen_supportbench():
    """LineageOS support threads: reply pairs from the Telegram archive."""
    path = HF_ROOT / "android" / "pavelshpagin__SupportBench" / "lineageos.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    messages = data["messages"] if isinstance(data, dict) else data
    by_id = {m.get("id"): m for m in messages if isinstance(m, dict)}
    for m in messages:
        if not isinstance(m, dict):
            continue
        reply_to = m.get("reply_to_id")
        body = FMT.normalize_text(m.get("body", ""))
        if not reply_to or not body:
            continue
        parent = by_id.get(reply_to)
        if not parent:
            continue
        question = FMT.normalize_text(parent.get("body", ""))
        if not question or question == body:
            continue
        yield rec(SYSTEM_LINEAGEOS, question, body)


def _kernel_vuln_rows(path: Path):
    with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
        for row in csv.DictReader(handle):
            yield row


def _kernel_vuln_records_from_rows(rows):
    for row in rows:
        subsystem = row.get("subsystem") or row.get("subsystem_path") or "the kernel"
        bug_type = row.get("bug_type") or "defect"
        severity = row.get("severity_hint") or "unknown"
        cve = row.get("cve_id") or "none assigned"
        intro = row.get("introducing_commit") or "?"
        lifetime = row.get("lifetime_days") or "?"
        path_hint = row.get("subsystem_path") or subsystem
        keywords = row.get("keywords") or ""
        related = row.get("related_fixes") or ""

        q1 = (f"Why is commit {intro} in {subsystem} ({path_hint}) considered vulnerable?")
        a1 = (f"Commit {intro} introduced a {bug_type} in {path_hint} ({subsystem}). "
              f"Severity hint: {severity}. CVE: {cve}. The defect survived "
              f"{lifetime} days before being fixed"
              + (f", and it is related to {related}" if related else "") + "."
              + (f" Signals: {keywords}." if keywords else ""))
        yield rec(None, q1, a1)

        fixing = row.get("fixing_commit") or "?"
        subject = row.get("fix_subject") or "(no subject)"
        files = row.get("files_changed") or "?"
        ins = row.get("insertions") or "?"
        dele = row.get("deletions") or "?"
        stable = row.get("stable_versions") or ""
        q2 = f"How was the {bug_type} in {path_hint} fixed?"
        a2 = (f"Commit {fixing} fixed it: \"{subject}\" by "
              f"{row.get('fix_author') or 'an unknown author'}. It touched {files} "
              f"file(s), adding {ins} and removing {dele} line(s)."
              + (f" Backported to stable {stable}." if stable else ""))
        yield rec(None, q2, a2)


def _kernel_vuln_records(path: Path):
    yield from _kernel_vuln_records_from_rows(_kernel_vuln_rows(path))


def gen_kernel_vuln():
    for owner in ("quguanni__kernel-vuln-dataset", "pebblebed__kernel-vuln-dataset"):
        path = HF_ROOT / "linux_kernel" / owner / "vuln_commits_full.csv"
        if path.is_file():
            yield from _kernel_vuln_records(path)


def gen_kernel_vuln_full_sample():
    path = HF_ROOT / "linux_kernel" / "quguanni__kernel-vuln-dataset-full" / "sample.jsonl"
    if not path.is_file():
        return
    for row in read_jsonl(path):
        if "fixing_commit" in row:
            yield from _kernel_vuln_records_from_rows([row])
        elif row.get("diff_raw") or row.get("subject"):
            # git-commit shape: subject/body + the real patch in diff_raw
            subject = FMT.normalize_text(row.get("subject", ""))
            body = FMT.normalize_text(row.get("body", ""))
            diff = FMT.normalize_text(row.get("diff_raw", ""))
            label = row.get("label")
            author = row.get("author_name") or "unknown"
            stats = (f"{row.get('files_changed', '?')} file(s), "
                     f"+{row.get('insertions', '?')}/-{row.get('deletions', '?')}")
            user = (f"Analyze this Linux kernel commit for vulnerability relevance and "
                    f"explain the change.\n\nSubject: {subject}"
                    + (f"\n\nBody:\n{body}" if body else ""))
            assistant = (f"{subject}\n\nCommit {row.get('abbreviated_hash') or row.get('hash')} "
                         f"by {author} ({stats})."
                         + (f" Label: {label}." if label not in (None, "") else "")
                         + (f"\n\n{diff}" if diff else ""))
            if diff or body:
                yield rec(None, user, assistant)
                continue
        else:
            yield rec(None, "Explain this kernel vulnerability record.",
                      json.dumps(row, ensure_ascii=False)[:20000])


def gen_kernel_syzfix_sample():
    path = HF_ROOT / "linux_kernel" / "xiaoguangwang__syzfix-dataset" / "sample.jsonl"
    if not path.is_file():
        return
    for row in read_jsonl(path):
        messages = row.get("messages") or row.get("conversations")
        if isinstance(messages, list) and messages:
            mapped = []
            for m in messages:
                if not isinstance(m, dict):
                    mapped = []
                    break
                role = str(m.get("role", m.get("from", ""))).lower()
                role = {"human": "user", "gpt": "assistant", "agent": "assistant"}.get(role, role)
                text = FMT.normalize_text(m.get("content", m.get("value", "")))
                if role in ("system", "user", "assistant") and text:
                    mapped.append({"role": role, "content": text})
            if mapped:
                yield {"messages": mapped}
                continue
        crash = row.get("crash") or row.get("bug") or row.get("title") or row.get("subject")
        fix = row.get("fix") or row.get("patch") or row.get("diff") or row.get("solution")
        # syzfix-dataset shape: crash_report + final_patch_diff (+ metadata)
        if row.get("crash_report") and (row.get("final_patch_diff") or row.get("fix_commit_message")):
            title = FMT.normalize_text(row.get("title", "a kernel crash"))
            report = FMT.normalize_text(row.get("crash_report", ""))
            subsystem = row.get("subsystem") or "unknown subsystem"
            patch = FMT.normalize_text(row.get("final_patch_diff", ""))
            message = FMT.normalize_text(row.get("fix_commit_message", ""))
            versions = row.get("num_patch_versions")
            discussion = " Reviewer discussion is included." if row.get("has_discussion") else ""
            user = (f"How do you fix this kernel crash?\n\n{title}\n"
                    f"(subsystem: {subsystem})\n\n{report[:6000]}")
            assistant = (f"{message}\n\n{patch}"
                         + (f"\n\n(patch went through {versions} revisions.)" if versions else "")
                         + discussion).strip()
            if assistant:
                yield rec(None, user, assistant)
                continue
        if crash and fix:
            yield rec(None, f"How do you fix this kernel crash?\n\n{FMT.normalize_text(crash)[:6000]}",
                      FMT.normalize_text(fix))
        else:
            yield rec(None, "How do you fix this kernel crash?",
                      json.dumps(row, ensure_ascii=False)[:20000])


def gen_mql5_benchmark():
    base = HF_ROOT / "mql5" / "CompilingThings__compile-benchmark"
    prompts = {r["item_id"]: r["prompt"] for r in read_jsonl(base / "prompts.jsonl")}
    verdicts = {}
    for name in ("per_item_results.jsonl", "bridge_q8_184_results.jsonl"):
        for row in read_jsonl(base / name):
            verdicts.setdefault(row.get("item_id"), []).append(row)
    for item_id, prompt in prompts.items():
        rows = verdicts.get(item_id, [])
        yield rec(None, FMT.normalize_text(prompt), verdict_sentence(rows))


def gen_mql5_repos():
    exts = {".mq5": "EA or script", ".mqh": "include header", ".mq4": "legacy EA"}
    for repo_dir in sorted(p for p in GH_ROOT.glob("mql5/*") if p.is_dir()):
        name = repo_dir.name.split("__", 1)[-1]
        for path in sorted(repo_dir.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            suffix = path.suffix.lower()
            if suffix in exts:
                text = FMT.normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
                if not text:
                    continue
                kind = exts[suffix]
                if suffix == ".mqh":
                    user = f"Show me the MQL5 header for {path.stem} from {name}."
                else:
                    user = f"Write an MQL5 {kind} that implements {path.stem} (from {name})."
                yield rec(None, user, text)
            elif path.name.lower() == "readme.md":
                text = FMT.normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
                if text:
                    yield rec(None, f"What does the MQL5 project {name} do, and how is it used?",
                              text)


def gen_security_qa():
    for dataset_dir in sorted(p for p in (HF_ROOT / "security").glob("*") if p.is_dir()):
        for csv_path in sorted(dataset_dir.glob("*.csv")):
            with csv_path.open(newline="", encoding="utf-8", errors="ignore") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    question = None
                    answer = None
                    for key, value in row.items():
                        low = (key or "").lower()
                        if question is None and "question" in low:
                            question = value
                        elif answer is None and "answer" in low:
                            answer = value
                    if question and answer:
                        yield rec(SYSTEM_SECURITY, FMT.normalize_text(question),
                                  FMT.normalize_text(answer))


_LOS_PROMPTS = {
    ".java": "Show me the Android 16 framework code for {module}.",
    ".kt": "Show me the Android 16 Kotlin code for {module}.",
    ".bp": "Write the Android.bp for {module}.",
    ".mk": "Write the Android.mk for {module}.",
    ".c": "Show me the C source for {module}.",
    ".h": "Show me the C header for {module}.",
    ".cpp": "Show me the C++ source for {module}.",
    ".te": "What SELinux rules does the A04s need for {module}?",
    ".rc": "Show me the init .rc definition for {module}.",
    ".sh": "Show me the shell script {module}.",
    ".py": "Show me the Python tool {module}.",
}


def gen_lineageos_tree(max_chars: int):
    catalog_path = LOS_ROOT / "_catalog.json"
    if not catalog_path.is_file():
        return
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    tree = Path(catalog["tree_root"])
    for entry in catalog["files"]:
        rel = entry["path"]
        suffix = entry["ext"]
        template = _LOS_PROMPTS.get(suffix)
        if not template:
            continue
        module = Path(rel).stem
        if rel.startswith("device/samsung/a04s"):
            user = f"How do I configure {module} for the Galaxy A04s ({rel})?"
        elif rel.startswith("kernel/samsung/exynos850"):
            user = f"Show me the Exynos850 kernel driver for {module} ({rel})."
        elif rel.startswith("vendor/samsung/a04s"):
            user = f"How is {module} configured in the A04s vendor tree ({rel})?"
        else:
            user = template.format(module=module) + f"  (path: {rel})"
        path = tree / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        text = FMT.normalize_text(text)
        if not text:
            continue
        if len(text) > max_chars:
            # keep whole files; the validator would reject them anyway
            continue
        yield rec(None, user, text)


def gen_codeparrot():
    path = HF_ROOT / "python" / "codeparrot__codeparrot-clean" / "sample.jsonl"
    if not path.is_file():
        return
    for row in read_jsonl(path):
        code = FMT.normalize_text(row.get("content", ""))
        if not code:
            continue
        repo = row.get("repo_name") or "a Python project"
        rel = row.get("path") or "module.py"
        license_id = row.get("license") or "unknown"
        user = (f"Write Python code that implements {Path(rel).name} "
                f"from {repo} (path: {rel}).")
        assistant = f"# {rel} (from {repo}, license: {license_id})\n\n{code}"
        yield rec(None, user, assistant)


GENERATORS = {
    "supportbench_lineageos": lambda args: gen_supportbench(),
    "kernel_vuln": lambda args: gen_kernel_vuln(),
    "kernel_syzfix_sample": lambda args: gen_kernel_syzfix_sample(),
    "kernel_vuln_full_sample": lambda args: gen_kernel_vuln_full_sample(),
    "mql5_benchmark": lambda args: gen_mql5_benchmark(),
    "mql5_repos": lambda args: gen_mql5_repos(),
    "security_qa": lambda args: gen_security_qa(),
    "lineageos_tree": lambda args: gen_lineageos_tree(args.max_chars),
    "python_codeparrot_sample": lambda args: gen_codeparrot(),
}


# ---------------------------------------------------------------- driver
def write_category(name, generator, formatted_root: Path, args) -> dict:
    import hashlib
    out_dir = formatted_root / name
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[bytes] = set()
    counts = {"train": 0, "val": 0}
    rejects = {r: 0 for r in FMT.REJECT_REASONS}
    train_hash, val_hash = hashlib.sha256(), hashlib.sha256()
    total = 0

    with (out_dir / "train.jsonl").open("wb") as train_f, \
         (out_dir / "val.jsonl").open("wb") as val_f:
        for raw in generator(args):
            total += 1
            canonical, reason = FMT.validate(raw["messages"], args.min_chars, args.max_chars)
            if reason:
                rejects[reason] += 1
                continue
            key = FMT.dedup_key(canonical["messages"], args.seed)
            if args.dedup and key in seen:
                rejects["duplicate"] += 1
                continue
            seen.add(key)
            payload = (json.dumps(canonical, ensure_ascii=False) + "\n").encode("utf-8")
            if FMT.split_assign(key, args.val_fraction):
                val_f.write(payload)
                val_hash.update(payload)
                counts["val"] += 1
            else:
                train_f.write(payload)
                train_hash.update(payload)
                counts["train"] += 1
            if args.max_records and counts["train"] + counts["val"] >= args.max_records:
                break

    manifest = {
        "category": name,
        "formatter_version": FMT.FORMATTER_VERSION + "+public",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "chat_template_source": "models/Qwen3.5-0.8B/tokenizer_config.json",
        "enable_thinking": args.enable_thinking,
        "seed": args.seed, "val_fraction": args.val_fraction, "dedup": args.dedup,
        "min_chars": args.min_chars, "max_chars": args.max_chars,
        "raw_records": total,
        "accepted": counts["train"] + counts["val"],
        "train_lines": counts["train"], "val_lines": counts["val"],
        "rejects": rejects,
        "train_sha256": train_hash.hexdigest(), "val_sha256": val_hash.hexdigest(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="format_public.py",
        description="Format Prompt-2 public sources into Qwen3.5 corpora.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--category", action="append", default=None)
    parser.add_argument("--all", action="store_true", help="Format every category")
    parser.add_argument("--list", action="store_true", help="List categories and exit")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--min-chars", type=int, default=None)
    parser.add_argument("--max-chars", type=int, default=None)
    parser.add_argument("--val-fraction", type=float, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-dedup", dest="dedup", action="store_false", default=None)
    parser.add_argument("--output-dir", default=None)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.list:
        for name in GENERATORS:
            print(name)
        return 0
    cfg = load_config(args.config)
    section = "Formatted_datasets"
    args.min_chars = args.min_chars if args.min_chars is not None else cfg.get_int(section, "min_chars", 32)
    args.max_chars = args.max_chars if args.max_chars is not None else cfg.get_int(section, "max_chars", 64000)
    args.val_fraction = (args.val_fraction if args.val_fraction is not None
                         else cfg.get_float(section, "val_fraction", 0.02))
    args.seed = args.seed if args.seed is not None else cfg.get_int(section, "seed", 42)
    args.dedup = cfg.get_bool(section, "dedup", True) if args.dedup is None else args.dedup
    args.enable_thinking = cfg.get_bool(section, "enable_thinking", False)
    formatted_root = (Path(args.output_dir) if args.output_dir
                      else cfg.path_for(section, "formatted_root", "datasets/formatted"))

    categories = list(GENERATORS) if (args.all or not args.category) else args.category
    unknown = [c for c in categories if c not in GENERATORS]
    if unknown:
        raise SystemExit(f"error: unknown category/categories: {', '.join(unknown)}")

    if args.dry_run:
        print(f"dry run: would format {len(categories)} categories into {formatted_root}/")
        for name in categories:
            print(f"  {name}")
        return 0

    failures = []
    for name in categories:
        manifest = write_category(name, GENERATORS[name], formatted_root, args)
        status = "ok" if manifest["train_lines"] > 0 else "EMPTY"
        print(f"{name:26} accepted={manifest['accepted']:>7} "
              f"train={manifest['train_lines']:>7} val={manifest['val_lines']:>5} "
              f"rejected={sum(manifest['rejects'].values()):>7}  {status}")
        if manifest["train_lines"] == 0:
            failures.append(name)
    if failures:
        print(f"\ncategories with no training rows: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
