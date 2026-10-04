#!/usr/bin/env python3
"""Inventory datasets/downloaded/ and write datasets/downloaded/_manifest.md.

For every dataset that the downloader logged OK it reports the local path,
file count, real on-disk bytes, file formats, and a record count (jsonl
lines, json array entries, parquet/arrow rows). It also flags categories
with fewer than MIN_EXAMPLES records and datasets that look unusable for
instruction tuning (raw corpora / classification-only).

Run:

    ./venv/bin/python scripts/dataset_inventory.py
    ./venv/bin/python scripts/dataset_inventory.py --fix-status
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config  # noqa: E402

DOWNLOADED = PROJECT_ROOT / "datasets" / "downloaded"
MIN_EXAMPLES = 500

INSTRUCTION_FIELDS = {
    "instruction", "instructions", "prompt", "prompts", "question", "questions",
    "query", "queries", "messages", "conversation", "conversations", "dialog",
    "dialogue", "input", "output", "response", "responses", "answer", "answers",
    "completion", "chosen", "rejected", "solution", "rationale", "think", "reasoning",
}
CLASSIFICATION_HINTS = {"label", "labels", "category", "class", "target", "sentiment"}
META_FIELDS = {"id", "idx", "index", "url", "source", "title", "meta", "metadata", "language", "lang", "date", "timestamp", "split"}


def load_downloader():
    path = PROJECT_ROOT / "datasets" / "scripts" / "downloader.py"
    spec = importlib.util.spec_from_file_location("moe_downloader", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["moe_downloader"] = module
    spec.loader.exec_module(module)
    return module


def parse_ok_log(path: Path) -> dict[str, int]:
    ok = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "OK":
            try:
                ok[parts[1]] = int(parts[2])
            except ValueError:
                ok[parts[1]] = 0
    return ok


def count_jsonl(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return None


def count_json(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            data = json.load(handle)
    except Exception:
        return count_jsonl(path)
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return len(value)
    return None


def count_parquet(path: Path) -> int | None:
    try:
        import pyarrow.parquet as pq
        return pq.read_metadata(path).num_rows
    except Exception:
        return None


def count_arrow(path: Path) -> int | None:
    try:
        import pyarrow as pa
    except Exception:
        return None
    for opener in (pa.ipc.open_file, pa.ipc.open_stream):
        try:
            with pa.memory_map(str(path), "r") as source:
                reader = opener(source)
                if hasattr(reader, "num_record_batches"):
                    return sum(reader.get_batch(i).num_rows
                               for i in range(reader.num_record_batches))
                return sum(batch.num_rows for batch in reader)
        except Exception:
            continue
    return None


def count_csv(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            n = sum(1 for line in handle if line.strip())
        return max(n - 1, 0)
    except OSError:
        return None


COUNT_BY_SUFFIX = {
    ".jsonl": count_jsonl,
    ".ndjson": count_jsonl,
    ".json": count_json,
    ".parquet": count_parquet,
    ".arrow": count_arrow,
    ".csv": count_csv,
}


def count_records(paths: list[Path]) -> tuple[int | None, int]:
    """Return (record_count, files_counted); None if nothing countable."""
    total, counted = 0, 0
    for path in paths:
        counter = COUNT_BY_SUFFIX.get(path.suffix.lower())
        if not counter:
            continue
        n = counter(path)
        if n is not None:
            total += n
            counted += 1
    return (total if counted else None), counted


def sample_fields(paths: list[Path]) -> list[str]:
    """Best-effort field names from the first data file found."""
    for path in paths:
        suffix = path.suffix.lower()
        try:
            if suffix in (".jsonl", ".ndjson"):
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        if line.strip():
                            row = json.loads(line)
                            if isinstance(row, dict):
                                return list(row.keys())
            elif suffix == ".json":
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    data = json.load(handle)
                rows = data if isinstance(data, list) else next(
                    (v for v in data.values() if isinstance(v, list)), []) if isinstance(data, dict) else []
                if rows and isinstance(rows[0], dict):
                    return list(rows[0].keys())
            elif suffix == ".parquet":
                import pyarrow.parquet as pq
                return list(pq.read_schema(path).names)
        except Exception:
            continue
    return []


def exclusion_reason(fields: list[str]) -> str | None:
    if not fields:
        return None
    lowered = {f.lower() for f in fields}
    if lowered & INSTRUCTION_FIELDS:
        return None
    if len(lowered) <= 3 and lowered & CLASSIFICATION_HINTS:
        return "classification-only (no instruction/response fields)"
    if lowered <= (META_FIELDS | {"text", "content", "code", "body", "document", "doc"}):
        return "raw corpus (no instruction/response fields)"
    return None


def human_gib(n: int) -> str:
    return f"{n / 1024 ** 3:.2f} GiB"


def audit(cfg: Config) -> dict:
    dl = load_downloader()
    source_list = cfg.path_for("Datasets", "source_list")
    root = cfg.path_for("Datasets", "downloaded_root",
                        cfg.get("Datasets", "download_root", "datasets/downloaded"))
    log_file = cfg.path_for("Datasets", "log_file")

    entries = dl.parse_source_list(source_list)
    category_of = {e["id"]: e["category"] for e in entries}
    ok_log = parse_ok_log(log_file)

    datasets, integrity, size_notes = [], [], []
    for repo_id, logged_bytes in sorted(ok_log.items()):
        category = category_of.get(repo_id, "uncategorized")
        local_dir = root / category / repo_id.replace("/", "__")
        files = [p for p in local_dir.rglob("*") if p.is_file() and ".cache" not in p.parts] if local_dir.is_dir() else []
        if not files:
            integrity.append(f"{repo_id}: logged OK but directory missing/empty ({local_dir})")
            continue
        disk_bytes = sum(p.stat().st_size for p in files)
        formats = defaultdict(int)
        for p in files:
            formats[p.suffix.lower() or "<none>"] += 1
        records, counted = count_records(files)
        fields = sample_fields(files)
        reason = exclusion_reason(fields)
        if logged_bytes and disk_bytes and logged_bytes > disk_bytes * 1.35:
            size_notes.append((logged_bytes - disk_bytes, repo_id, category))
        datasets.append({
            "id": repo_id, "category": category, "path": local_dir,
            "files": len(files), "bytes": disk_bytes,
            "formats": dict(sorted(formats.items(), key=lambda kv: -kv[1])),
            "records": records, "counted_files": counted,
            "fields": fields, "exclusion": reason,
        })

    # Directories on disk that were not logged
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for sub in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
            owner, _, name = sub.name.partition("__")
            if f"{owner}/{name}" not in ok_log:
                integrity.append(f"on-disk dir not in OK log: {sub}")

    size_notes.sort(reverse=True)
    return {"datasets": datasets, "integrity": integrity, "size_notes": size_notes}


def write_manifest(result: dict, cfg: Config) -> Path:
    datasets = result["datasets"]
    default_manifest = cfg.path_for("Datasets", "downloaded_root",
                                    cfg.get("Datasets", "download_root", "datasets/downloaded")) / "_manifest.md"
    out = cfg.path_for("Datasets", "manifest", str(default_manifest))
    by_category = defaultdict(list)
    for row in datasets:
        by_category[row["category"]].append(row)

    lines = [
        "# Dataset manifest",
        "",
        f"Generated: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        f"Source list: `{cfg.path_for('Datasets', 'source_list')}`",
        f"Download root: `{cfg.path_for('Datasets', 'download_root')}`",
        f"Datasets: {len(datasets)} across {len(by_category)} categories",
        "",
        "Record counts are read from file metadata (jsonl lines, json arrays,",
        "parquet/arrow row counts). `-` means no countable data file.",
        "",
    ]
    for category in sorted(by_category):
        rows = sorted(by_category[category], key=lambda r: r["id"])
        total_bytes = sum(r["bytes"] for r in rows)
        total_records = sum(r["records"] or 0 for r in rows)
        flag = "  **< 500 examples — needs more data**" if total_records < MIN_EXAMPLES else ""
        lines += [
            f"## {category}",
            "",
            f"{len(rows)} datasets · {human_gib(total_bytes)} · "
            f"~{total_records:,} records{flag}",
            "",
            "| dataset | local path | files | size | formats | records |",
            "|---|---|---:|---:|---|---:|",
        ]
        for row in rows:
            rel = row["path"].relative_to(PROJECT_ROOT)
            formats = ", ".join(row["formats"].keys()) or "-"
            records = f"{row['records']:,}" if row["records"] is not None else "-"
            lines.append(f"| `{row['id']}` | `{rel}` | {row['files']} | "
                         f"{human_gib(row['bytes'])} | {formats} | {records} |")
        lines.append("")

    exclusions = [r for r in datasets if r["exclusion"]]
    lines += ["## Candidates for exclusion", ""]
    if exclusions:
        lines += ["Heuristic: no instruction/response-shaped fields were found.", ""]
        for row in exclusions:
            lines.append(f"- `{row['id']}` ({row['category']}): {row['exclusion']}")
    else:
        lines.append("None detected.")
    lines.append("")
    no_data = [r for r in datasets if r["records"] is None]
    lines += ["## Datasets with no countable data files", ""]
    if no_data:
        lines += ["These repos downloaded README/config files but no data file the",
                  "inventory can count (parquet/jsonl/json/arrow/csv).", ""]
        lines += [f"- `{r['id']}` ({r['category']}) — {r['files']} files, "
                  f"{human_gib(r['bytes'])}" for r in no_data]
    else:
        lines.append("None.")
    lines.append("")
    lines += ["## Integrity", ""]
    if result["integrity"]:
        lines += [f"- {a}" for a in result["integrity"]]
    else:
        lines.append("No missing, empty, or untracked dataset directories.")
    lines += ["", "## Size notes", "",
              "The historical `OK` byte count came from the HF API's `usedStorage`,",
              "which counts total repo storage and overstates what was actually",
              "fetched. Real on-disk sizes are used in the tables above.", ""]
    if result["size_notes"]:
        top_gap, top_id, _ = result["size_notes"][0]
        lines.append(f"- {len(result['size_notes'])} datasets: API estimate > 1.35x on-disk "
                     f"(largest gap: `{top_id}`, {human_gib(top_gap)} over).")
    else:
        lines.append("None.")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def fix_status(cfg: Config, datasets: list[dict]) -> Path:
    """Rewrite _status.json with real on-disk bytes alongside the logged estimate."""
    status_file = cfg.path_for("Datasets", "status_file")
    log_file = cfg.path_for("Datasets", "log_file")
    status = json.loads(status_file.read_text(encoding="utf-8"))
    per_category = defaultdict(lambda: {"ok": 0, "failed": 0})
    for row in datasets:
        per_category[row["category"]]["ok"] += 1
    # The log's OK lines hold the byte figure the run recorded (the HF API
    # usedStorage estimate for the historical run).
    status["bytes_api_estimate"] = sum(parse_ok_log(log_file).values())
    status["bytes"] = sum(r["bytes"] for r in datasets)
    status["per_category"] = {k: dict(v) for k, v in sorted(per_category.items())}
    status["bytes_note"] = "bytes = actual on-disk; bytes_api_estimate = HF usedStorage sum"
    status_file.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status_file


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inventory datasets/downloaded/")
    parser.add_argument("--config", default=None)
    parser.add_argument("--fix-status", action="store_true",
                        help="Rewrite _status.json bytes to real on-disk totals")
    args = parser.parse_args(argv)

    config_path = Path(args.config) if args.config else PROJECT_ROOT / "config.md"
    cfg = Config.load(config_path)
    result = audit(cfg)
    manifest = write_manifest(result, cfg)

    by_category = defaultdict(lambda: [0, 0, 0])
    for row in result["datasets"]:
        b = by_category[row["category"]]
        b[0] += 1
        b[1] += row["bytes"]
        b[2] += row["records"] or 0

    print(f"manifest: {manifest}")
    print(f"{'category':24} {'datasets':>8} {'size':>10} {'records':>12}  flag")
    for category in sorted(by_category):
        n, size, records = by_category[category]
        flag = "LOW (<500)" if records < MIN_EXAMPLES else ""
        print(f"{category:24} {n:>8} {human_gib(size):>10} {records:>12,}  {flag}")
    print(f"\nintegrity issues: {len(result['integrity'])}")
    for a in result["integrity"][:5]:
        print(f"  - {a}")
    print(f"size notes (API overstatement): {len(result['size_notes'])} datasets")
    if args.fix_status:
        print(f"status rewritten: {fix_status(cfg, result['datasets'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
