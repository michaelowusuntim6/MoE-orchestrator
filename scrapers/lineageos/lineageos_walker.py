#!/usr/bin/env python3
"""Walk the LineageOS source tree and build a file catalog.

The tree is **read only** — this script never writes inside
`lineageos_tree_root`; the catalog lands under `lineageos_output_root`.

Tunables come from config.md `## Scrapers`:
lineageos_tree_root, lineageos_max_file_mb, lineageos_include_extensions,
lineageos_skip_dirs, lineageos_max_files.

    ./venv-inference/bin/python scrapers/lineageos/lineageos_walker.py --dry-run
    ./venv-inference/bin/python scrapers/lineageos/lineageos_walker.py --sample 500
    ./venv-inference/bin/python scrapers/lineageos/lineageos_walker.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import human_bytes, load_config, over_file_limit  # noqa: E402

# Device-specific areas are walked first so a truncated catalog still contains
# the most relevant code for the target device (Galaxy A04s / Exynos850).
PRIORITY_PREFIXES = (
    "device/samsung/a04s",
    "kernel/samsung/exynos850",
    "vendor/samsung/a04s",
    "kernel/samsung/a04s",
    "device/samsung",
    "vendor/samsung",
    "kernel/samsung",
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="lineageos_walker.py",
        description="Catalog the LineageOS tree (read-only).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Count matching files without hashing")
    parser.add_argument("--sample", type=int, default=None,
                        help="Hash only the first N files (fast preview)")
    parser.add_argument("--root", default=None, help="Override lineageos_tree_root")
    parser.add_argument("--output", default=None, help="Override the catalog path")
    parser.add_argument("--max-files", type=int, default=None,
                        help="Override lineageos_max_files")
    parser.add_argument("--catalog", action="store_true",
                        help="Write the catalog JSON (default behavior)")
    return parser.parse_args(argv)


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def is_priority(rel: str) -> bool:
    return rel.startswith(PRIORITY_PREFIXES)


def walk(root: Path, include_ext, skip_dirs, max_file_mb):
    """Yield (rel_path, size, priority) for every matching file, priority first."""
    skip = set(skip_dirs)
    ext = {e.lower() for e in include_ext}
    priority, rest, skipped_large = [], [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skipped directories in place so .repo/out/prebuilts are never
        # traversed (this is what keeps a dry run fast on a 100+ GB tree)
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.suffix.lower() not in ext:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if over_file_limit(size, max_file_mb):
                skipped_large += 1
                continue
            rel = str(path.relative_to(root))
            (priority if is_priority(rel) else rest).append((rel, size))
    return priority, rest, skipped_large


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    scrapers = "Scrapers"

    root = Path(args.root).expanduser() if args.root else cfg.path_for(
        scrapers, "lineageos_tree_root")
    output_root = cfg.path_for(scrapers, "lineageos_output_root",
                               "datasets/public/lineageos_tree")
    catalog_path = Path(args.output) if args.output else output_root / "_catalog.json"
    max_file_mb = cfg.get_int(scrapers, "lineageos_max_file_mb", 10)
    max_files = args.max_files or cfg.get_int(scrapers, "lineageos_max_files", 200000)
    include_ext = cfg.get_list(scrapers, "lineageos_include_extensions")
    skip_dirs = cfg.get_list(scrapers, "lineageos_skip_dirs")

    if not root.is_dir():
        raise SystemExit(f"error: LineageOS tree not found: {root}")

    print(f"tree root    : {root}")
    print(f"catalog      : {catalog_path}")
    print(f"extensions   : {', '.join(include_ext)}")
    print(f"skip dirs    : {', '.join(skip_dirs)}")
    print(f"max file     : {max_file_mb} MB   max files: {max_files}")
    print("mode         : " + ("dry-run (count only)" if args.dry_run else
                               f"sample ({args.sample} files hashed)" if args.sample
                               else "full (hash every file)"))

    priority, rest, skipped_large = walk(root, include_ext, skip_dirs, max_file_mb)
    priority.sort()
    rest.sort()
    ordered = priority + rest
    if len(ordered) > max_files:
        ordered = ordered[:max_files]

    total_bytes = sum(size for _, size in ordered)
    ext_counts = Counter(Path(rel).suffix.lower() for rel, _ in ordered)
    print(f"\nmatched files: {len(ordered)}  ({human_bytes(total_bytes)})")
    print(f"priority files (a04s/exynos850/samsung): {len(priority)}")
    print(f"skipped > {max_file_mb} MB: {skipped_large}")
    print("top extensions: " + ", ".join(
        f"{ext}={n}" for ext, n in ext_counts.most_common(8)))

    if args.dry_run:
        print("\n--dry-run: would hash and catalog the files above "
              "(no hashing performed, tree untouched)")
        return 0

    limit = args.sample if args.sample else len(ordered)
    files = []
    for i, (rel, size) in enumerate(ordered):
        entry = {"path": rel, "size": size, "ext": Path(rel).suffix.lower(),
                 "priority": is_priority(rel)}
        if i < limit:
            entry["sha256"] = sha256_of(root / rel)
        files.append(entry)
        if (i + 1) % 5000 == 0:
            print(f"progress: {i + 1}/{len(ordered)}")

    catalog = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "tree_root": str(root),
        "read_only": True,
        "include_extensions": include_ext,
        "skip_dirs": skip_dirs,
        "max_file_mb": max_file_mb,
        "max_files": max_files,
        "hashed": limit,
        "matched_files": len(ordered),
        "matched_bytes": total_bytes,
        "skipped_large_files": skipped_large,
        "extension_counts": dict(ext_counts),
        "files": files,
    }
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"\ncatalog written: {catalog_path} ({human_bytes(total_bytes)} catalogued)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
