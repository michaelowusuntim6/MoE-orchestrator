#!/usr/bin/env python3
"""Extract AOSP-derived source snippets from the local LineageOS tree.

The LineageOS tree *is* an AOSP fork, so the highest-fidelity AOSP snippets
for this project are already on disk. This scraper reads them (never writes
to the tree) and emits snippet records that can be turned into training pairs.

No network access: everything comes from `lineageos_tree_root` (config.md
`## Scrapers`). `--allow-remote` is reserved for a future addition.

    ./venv-inference/bin/python scrapers/lineageos/aosp_scraper.py --dry-run
    ./venv-inference/bin/python scrapers/lineageos/aosp_scraper.py \
        --path frameworks/base/core/java/android/os --limit 50
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import human_bytes, load_config, over_file_limit  # noqa: E402

DEFAULT_PATHS = (
    "frameworks/base/core/java/android",
    "frameworks/base/services/core/java/com/android/server",
    "system/core",
    "libcore",
    "packages/modules",
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="aosp_scraper.py",
        description="Extract AOSP source snippets from the local tree (read-only).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--path", action="append", default=None,
                        help="Tree-relative path to scan (repeatable)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be extracted; write nothing")
    parser.add_argument("--limit", type=int, default=200,
                        help="Max snippet records to emit")
    parser.add_argument("--output", default=None, help="Override output JSONL path")
    parser.add_argument("--allow-remote", action="store_true",
                        help="Reserved: fetch from android.googlesource.com (unimplemented)")
    return parser.parse_args(argv)


def snippet_record(rel: str, text: str, kind: str) -> dict:
    return {
        "messages": [
            {"role": "user",
             "content": f"Explain this AOSP source file and what it does: {rel}"},
            {"role": "assistant", "content": text},
        ],
        "source_path": rel,
        "kind": kind,
    }


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    scrapers = "Scrapers"

    root = cfg.path_for(scrapers, "lineageos_tree_root")
    output_root = cfg.path_for(scrapers, "lineageos_output_root",
                               "datasets/public/lineageos_tree")
    out_path = Path(args.output) if args.output else output_root / "aosp_snippets.jsonl"
    max_file_mb = cfg.get_int(scrapers, "lineageos_max_file_mb", 10)
    include_ext = {e.lower() for e in cfg.get_list(scrapers, "lineageos_include_extensions")}
    skip_dirs = set(cfg.get_list(scrapers, "lineageos_skip_dirs"))
    paths = args.path or list(DEFAULT_PATHS)

    if not root.is_dir():
        raise SystemExit(f"error: LineageOS tree not found: {root}")
    if args.allow_remote:
        print("note: --allow-remote is reserved; this build reads the local tree only")

    print(f"tree root : {root}")
    print(f"output    : {out_path}")
    print(f"scanning  : {', '.join(paths)}")
    print(f"limit     : {args.limit} snippets   max file: {max_file_mb} MB")

    found = []
    for rel_root in paths:
        base = root / rel_root
        if not base.is_dir():
            print(f"  {rel_root:60} (not present)")
            continue
        count = 0
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.relative_to(root).parts):
                continue
            if path.suffix.lower() not in include_ext:
                continue
            size = path.stat().st_size
            if over_file_limit(size, max_file_mb):
                continue
            found.append((str(path.relative_to(root)), size))
            count += 1
            if len(found) >= args.limit:
                break
        print(f"  {rel_root:60} {count} files")
        if len(found) >= args.limit:
            break

    total = sum(size for _, size in found)
    print(f"\ncandidate files: {len(found)}  ({human_bytes(total)})")

    if args.dry_run:
        print("\n--dry-run: would emit user/assistant snippet records for these files")
        for rel, size in found[:10]:
            print(f"  {rel}  ({human_bytes(size)})")
        if len(found) > 10:
            print(f"  ... and {len(found) - 10} more")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for rel, _size in found:
            try:
                text = (root / rel).read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if not text:
                continue
            handle.write(json.dumps(snippet_record(rel, text, Path(rel).suffix.lstrip(".")),
                                    ensure_ascii=False) + "\n")
            written += 1
    print(f"\nwrote {written} snippets -> {out_path}")
    print(f"generated: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
