#!/usr/bin/env python3
"""Download the datasets listed in scrapers/huggingface/dataset_list.md.

Guards (all from config.md `## Scrapers`):
  * per-file ceiling   hf_max_file_mb   (default 500 MB)
  * per-dataset ceiling hf_max_dataset_mb (default 5120 MB)
  * gated datasets      hf_skip_gated
  * `--allow-large` overrides both size ceilings (never the gated rule).

Resumable: a dataset directory that already contains files is skipped.

    ./venv-inference/bin/python scrapers/huggingface/hf_downloader.py --dry-run
    ./venv-inference/bin/python scrapers/huggingface/hf_downloader.py --category android
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import (  # noqa: E402
    MB, RunLog, dir_has_files, dir_size, human_bytes, load_config, now_iso,
    over_file_limit, write_status,
)

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*/[A-Za-z0-9][A-Za-z0-9._\-]*$")

_SNAPSHOT_SNIPPET = (
    "import sys\n"
    "from huggingface_hub import snapshot_download\n"
    "repo, dest = sys.argv[1], sys.argv[2]\n"
    "snapshot_download(repo_id=repo, repo_type='dataset', local_dir=dest)\n"
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="hf_downloader.py",
        description="Download datasets from scrapers/huggingface/dataset_list.md",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve and report decisions; download nothing")
    parser.add_argument("--category", action="append", default=None,
                        help="Restrict to one category (repeatable)")
    parser.add_argument("--dataset", action="append", default=None,
                        help="Restrict to one dataset id (repeatable)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N datasets")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if the directory already has files")
    parser.add_argument("--allow-large", action="store_true",
                        help="Ignore the file/dataset size ceilings")
    return parser.parse_args(argv)


def parse_dataset_list(path: Path) -> list[tuple[str, str]]:
    """Return [(category, dataset_id)]. Supports `## cat` and `category: cat`."""
    entries, category = [], "uncategorized"
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("# ") or line.startswith("#!"):
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
        if ID_RE.match(line):
            entries.append((category, line))
    return entries


def open_log(cfg) -> RunLog:
    return RunLog(cfg.path_for("Scrapers", "download_log_file",
                               "scrapers/logs/download.log"))


def dataset_meta(api, repo_id: str, token):
    """(total_bytes, gated, largest_file_bytes, error)."""
    try:
        info = api.dataset_info(repo_id, files_metadata=True, token=token)
    except Exception as exc:
        return None, None, None, f"{type(exc).__name__}: {exc}"
    sizes = [getattr(s, "size", None) for s in (info.siblings or [])]
    sizes = [s for s in sizes if isinstance(s, int)]
    return (sum(sizes) if sizes else None,
            bool(getattr(info, "gated", False)),
            (max(sizes) if sizes else None),
            None)


def snapshot_to_dir(repo_id: str, dest: Path, token, timeout: int) -> None:
    env = dict(os.environ)
    if token:
        env["HF_TOKEN"] = token
    dest.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([sys.executable, "-c", _SNAPSHOT_SNIPPET, repo_id, str(dest)],
                          env=env, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError(tail[-1] if tail else f"exit {proc.returncode}")


def download_dataset(cfg, repo_id: str, category: str, log: RunLog,
                     force: bool = False, dry_run: bool = False,
                     allow_large: bool = False, api=None, token=None) -> dict:
    """Download one dataset with all guards. Returns a result dict."""
    scrapers = "Scrapers"
    output_root = cfg.path_for(scrapers, "hf_output_root", "datasets/public/huggingface")
    dest = output_root / category / repo_id.replace("/", "__")
    max_file_mb = cfg.get_int(scrapers, "hf_max_file_mb", 500)
    max_dataset_mb = cfg.get_int(scrapers, "hf_max_dataset_mb", 5120)
    skip_gated = cfg.get_bool(scrapers, "hf_skip_gated", True)
    timeout = cfg.get_int(scrapers, "download_timeout_seconds",
                          cfg.get_int(scrapers, "timeout_seconds", 900))
    attempts = cfg.get_int(scrapers, "download_retry_attempts", 4)
    backoff = cfg.get_float(scrapers, "download_retry_backoff_seconds", 3)
    token = token or os.environ.get(cfg.get_str(scrapers, "hf_token_env", "HF_TOKEN")) or None

    result = {"dataset": repo_id, "category": category, "path": str(dest),
              "action": None, "reason": "", "bytes": 0}

    if not force and dir_has_files(dest):
        result.update(action="skip", reason="already_downloaded")
        return result

    if api is None:
        from huggingface_hub import HfApi
        api = HfApi()
    total, gated, biggest, err = dataset_meta(api, repo_id, token)
    result["size_bytes"] = total
    if err:
        result.update(action="fail", reason=f"api_error: {err}")
        return result
    if gated and skip_gated:
        result.update(action="skip", reason="gated")
        return result
    if not allow_large:
        if total is not None and total > max_dataset_mb * MB:
            result.update(action="skip", reason=f"dataset_too_large ({human_bytes(total)})")
            return result
        if over_file_limit(biggest, max_file_mb):
            result.update(action="skip", reason=f"file_too_large ({human_bytes(biggest)})")
            return result

    if dry_run:
        result.update(action="download", reason="dry-run")
        return result

    started = time.time()
    last_error = "unknown"
    for attempt in range(1, max(1, attempts) + 1):
        try:
            snapshot_to_dir(repo_id, dest, token, timeout)
            result.update(action="ok", bytes=dir_size(dest),
                          seconds=round(time.time() - started, 1))
            return result
        except subprocess.TimeoutExpired:
            last_error = f"timeout after {timeout}s"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < attempts:
            time.sleep(backoff * (2 ** (attempt - 1)))
    result.update(action="fail", reason=last_error)
    return result


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    scrapers = "Scrapers"
    list_path = cfg.path_for(scrapers, "hf_dataset_list_file",
                             "scrapers/huggingface/dataset_list.md")
    status_path = cfg.path_for(scrapers, "download_status_file",
                               "scrapers/logs/status.json")
    if not list_path.is_file():
        raise SystemExit(f"error: dataset list not found: {list_path}")

    entries = parse_dataset_list(list_path)
    if args.category:
        entries = [e for e in entries if e[0] in set(args.category)]
    if args.dataset:
        wanted = set(args.dataset)
        entries = [e for e in entries if e[1] in wanted]
    if args.limit:
        entries = entries[: args.limit]
    if not entries:
        raise SystemExit("error: no datasets matched the filters")

    print(f"dataset list : {list_path}")
    print(f"output root  : {cfg.path_for(scrapers, 'hf_output_root')}")
    print(f"datasets     : {len(entries)} across "
          f"{len({c for c, _ in entries})} categories")
    print(f"guards       : file <= {cfg.get_int(scrapers,'hf_max_file_mb',500)} MB, "
          f"dataset <= {cfg.get_int(scrapers,'hf_max_dataset_mb',5120)} MB, "
          f"skip_gated={cfg.get_bool(scrapers,'hf_skip_gated',True)}"
          + (" [--allow-large]" if args.allow_large else ""))

    started_at = now_iso()

    if args.dry_run:
        print("\n--dry-run: would query the HF API and then download:")
        for category, rid in entries:
            print(f"  {category:16} {rid}")
        print(f"\nwould write to {cfg.path_for(scrapers, 'hf_output_root')}/<category>/<owner>__<name>/")
        print(f"this dry run made no API calls and downloaded nothing")
        return 0

    from huggingface_hub import HfApi
    api = HfApi()
    log = open_log(cfg)
    counters = {"total": len(entries), "ok": 0, "skipped": 0, "failed": 0, "bytes": 0}
    rows = []
    try:
        for i, (category, rid) in enumerate(entries, 1):
            res = download_dataset(cfg, rid, category, log, force=args.force,
                                   dry_run=False, allow_large=args.allow_large, api=api)
            rows.append(res)
            if res["action"] == "ok":
                counters["ok"] += 1
                counters["bytes"] += res.get("bytes", 0)
                log.write(f"OK {rid} {res.get('bytes',0)} {res.get('seconds',0)}")
            elif res["action"] == "skip":
                counters["skipped"] += 1
                log.write(f"SKIP {rid} {res['reason']}")
            else:
                counters["failed"] += 1
                log.write(f"FAIL {rid} {res['reason']}")
            if i % 5 == 0 or i == len(entries):
                print(f"progress: {i}/{len(entries)}  ok={counters['ok']} "
                      f"skipped={counters['skipped']} failed={counters['failed']}")
    finally:
        log.close()

    out = write_status(status_path, started_at, counters,
                       {"datasets": rows, "output_root":
                        str(cfg.path_for(scrapers, "hf_output_root"))})
    print(f"\n=== summary ===\n" + "\n".join(
        f"{k:8}: {human_bytes(v) if k == 'bytes' else v}" for k, v in counters.items()))
    print(f"log    : {cfg.path_for(scrapers, 'download_log_file')}")
    print(f"status : {out}")
    return 1 if counters["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
