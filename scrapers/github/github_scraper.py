#!/usr/bin/env python3
"""Clone the repositories listed in scrapers/github/repo_list.md.

Guards (config.md `## Scrapers`):
  * github_skip_forks / github_skip_archived
  * github_max_repo_mb (default 2048) — skipped unless `--allow-large`
  * github_max_file_mb (default 500) — oversized **files** are deleted after
    the clone and recorded in `_truncated.json`

    ./venv-inference/bin/python scrapers/github/github_scraper.py --dry-run
    ./venv-inference/bin/python scrapers/github/github_scraper.py --category mql5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import (  # noqa: E402
    MB, RunLog, dir_has_files, dir_size, human_bytes, load_config, now_iso,
    over_file_limit, write_status,
)

REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*/[A-Za-z0-9][A-Za-z0-9._\-]*$")
API = "https://api.github.com/repos/{repo}"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="github_scraper.py",
        description="Clone repos from scrapers/github/repo_list.md",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be cloned; no API calls, no clones")
    parser.add_argument("--category", action="append", default=None)
    parser.add_argument("--repo", action="append", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true",
                        help="Re-clone even if the directory already has files")
    parser.add_argument("--allow-large", action="store_true",
                        help="Ignore the repo/file size ceilings")
    parser.add_argument("--all", action="store_true",
                        help="Process every entry in the list (the default behavior)")
    return parser.parse_args(argv)


def parse_repo_list(path: Path) -> list[tuple[str, str]]:
    entries, category = [], "uncategorized"
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            category = line[3:].strip()
            continue
        if line.startswith("#"):
            continue
        m = re.match(r"^category\s*:\s*(\S+)$", line)
        if m:
            category = m.group(1)
            continue
        if REPO_RE.match(line):
            entries.append((category, line))
    return entries


def repo_metadata(repo: str, token: str | None):
    """(size_kb, default_branch, archived, fork, error) from the GitHub API."""
    import requests
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(API.format(repo=repo), headers=headers, timeout=30)
    except Exception as exc:
        return None, None, None, None, f"{type(exc).__name__}: {exc}"
    if response.status_code == 404:
        return None, None, None, None, "not_found"
    if response.status_code >= 400:
        return None, None, None, None, f"HTTP {response.status_code}"
    data = response.json()
    return (data.get("size"), data.get("default_branch"),
            bool(data.get("archived")), bool(data.get("fork")), None)


def prune_large_files(root: Path, max_file_mb: int) -> list[dict]:
    """Delete files over the ceiling; return the deletion record."""
    removed = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if over_file_limit(path.stat().st_size, max_file_mb):
            removed.append({"path": str(path.relative_to(root)),
                            "bytes": path.stat().st_size})
            path.unlink()
    if removed:
        (root / "_truncated.json").write_text(
            json.dumps({"max_file_mb": max_file_mb, "removed": removed}, indent=2),
            encoding="utf-8")
    return removed


def clone_repo(repo: str, dest: Path, depth: int, timeout: int, token: str | None) -> None:
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{repo}.git"
    env = dict(os.environ)
    if token:  # token in the URL keeps it out of the process list
        url = f"https://x-access-token:{token}@github.com/{repo}.git"
    proc = subprocess.run(["git", "clone", "--depth", str(max(1, depth)), url, str(dest)],
                          env=env, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError(tail[-1] if tail else f"git exit {proc.returncode}")


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    scrapers = "Scrapers"
    list_path = cfg.path_for(scrapers, "github_repos_file", "scrapers/github/repo_list.md")
    if not list_path.is_file():
        raise SystemExit(f"error: repo list not found: {list_path}")

    entries = parse_repo_list(list_path)
    if args.category:
        entries = [e for e in entries if e[0] in set(args.category)]
    if args.repo:
        entries = [e for e in entries if e[1] in set(args.repo)]
    if args.limit:
        entries = entries[: args.limit]
    if not entries:
        raise SystemExit("error: no repos matched the filters")

    output_root = cfg.path_for(scrapers, "github_output_root", "datasets/public/github")
    max_repo_mb = cfg.get_int(scrapers, "github_max_repo_mb", 2048)
    max_file_mb = cfg.get_int(scrapers, "github_max_file_mb", 500)
    depth = cfg.get_int(scrapers, "github_clone_depth", 1)
    timeout = cfg.get_int(scrapers, "github_timeout_seconds", 600)
    skip_forks = cfg.get_bool(scrapers, "github_skip_forks", True)
    skip_archived = cfg.get_bool(scrapers, "github_skip_archived", False)
    token = os.environ.get(cfg.get_str(scrapers, "github_token_env", "GITHUB_TOKEN")) or None

    print(f"repo list    : {list_path}")
    print(f"output root  : {output_root}")
    print(f"repos        : {len(entries)} across {len({c for c, _ in entries})} categories")
    print(f"guards       : repo <= {max_repo_mb} MB, file <= {max_file_mb} MB, "
          f"skip_forks={skip_forks}, skip_archived={skip_archived}, depth={depth}"
          + (" [--allow-large]" if args.allow_large else ""))
    print(f"token        : {'set' if token else 'not set (60 req/h unauthenticated)'}")

    if args.dry_run:
        print("\n--dry-run: would query the GitHub API and then clone:")
        for category, repo in entries:
            print(f"  {category:16} {repo}")
        print(f"\nwould write to {output_root}/<category>/<owner>__<name>/")
        print("this dry run made no API calls and cloned nothing")
        return 0

    log = RunLog(cfg.path_for(scrapers, "download_log_file", "scrapers/logs/download.log"))
    counters = {"total": len(entries), "ok": 0, "skipped": 0, "failed": 0, "bytes": 0,
                "files_removed": 0}
    rows = []
    started_at = now_iso()
    try:
        for i, (category, repo) in enumerate(entries, 1):
            dest = output_root / category / repo.replace("/", "__")
            row = {"repo": repo, "category": category, "path": str(dest), "action": None,
                   "reason": ""}
            if not args.force and dir_has_files(dest):
                row.update(action="skip", reason="already_cloned")
            else:
                size_kb, branch, archived, fork, err = repo_metadata(repo, token)
                if err:
                    row.update(action="fail", reason=f"api_error: {err}")
                elif fork and skip_forks:
                    row.update(action="skip", reason="fork")
                elif archived and skip_archived:
                    row.update(action="skip", reason="archived")
                elif not args.allow_large and size_kb is not None and size_kb / 1024 > max_repo_mb:
                    row.update(action="skip",
                               reason=f"repo_too_large ({size_kb/1024:.0f} MB)")
                else:
                    try:
                        clone_repo(repo, dest, depth, timeout, token)
                        removed = [] if args.allow_large else prune_large_files(dest, max_file_mb)
                        counters["files_removed"] += len(removed)
                        row.update(action="ok", bytes=dir_size(dest),
                                   default_branch=branch, archived=archived, fork=fork,
                                   files_removed=len(removed))
                    except Exception as exc:
                        row.update(action="fail", reason=f"{type(exc).__name__}: {exc}")

            rows.append(row)
            if row["action"] == "ok":
                counters["ok"] += 1
                counters["bytes"] += row.get("bytes", 0)
                log.write(f"OK {repo} {row.get('bytes',0)} removed={row.get('files_removed',0)}")
            elif row["action"] == "skip":
                counters["skipped"] += 1
                log.write(f"SKIP {repo} {row['reason']}")
            else:
                counters["failed"] += 1
                log.write(f"FAIL {repo} {row['reason']}")
            if i % 5 == 0 or i == len(entries):
                print(f"progress: {i}/{len(entries)}  ok={counters['ok']} "
                      f"skipped={counters['skipped']} failed={counters['failed']}")
    finally:
        log.close()

    status = write_status(cfg.path_for(scrapers, "download_status_file"), started_at,
                          counters, {"repos": rows, "output_root": str(output_root)})
    print("\n=== summary ===")
    for key, value in counters.items():
        print(f"{key:14}: {human_bytes(value) if key == 'bytes' else value}")
    print(f"status : {status}")
    return 1 if counters["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
