#!/usr/bin/env python3
"""Dataset downloader for the MoE orchestrator.

Reads every tunable from config.md, reads the vetted dataset list from
datasets/sources/ReallyHelpfulClean.md, queries the HuggingFace API for
size + gated status, and downloads survivors with ``snapshot_download``
into ``datasets/downloaded/<category>/<owner>__<name>/``.

Safe defaults:
  * ``--dry-run`` lists every decision and downloads nothing.
  * Downloads run in a subprocess with a hard wall-clock timeout.
  * Every failure is logged and skipped; a dataset never aborts the run.
  * Re-running resumes: any dataset directory that already has files is
    skipped.

Run ``python datasets/scripts/downloader.py --help`` for flags.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config.md"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config, ConfigError, parse_config  # noqa: E402

API_URL = "https://huggingface.co/api/datasets/{repo_id}"
API_TIMEOUT = 30

# "- owner/name — free text" (em dash separates id from the description).
DATASET_LINE_RE = re.compile(
    r"^-\s+([A-Za-z0-9][A-Za-z0-9._\-]*/[A-Za-z0-9][A-Za-z0-9._\-]*)"
    r"\s+\u2014\s*(.*)$"
)
SIZE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(TB|GB|MB|KB|B)\b", re.IGNORECASE)
SIZE_UNITS = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}

_LOG_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def human_bytes(n) -> str:
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


# config.md parsing lives in orchestrator/config.py and is re-exported here
# (Config, ConfigError, parse_config) so existing imports keep working.


# --------------------------------------------------------------------------
# source list parsing
# --------------------------------------------------------------------------
def parse_source_list(path: Path) -> list[dict]:
    """Extract dataset ids from `- owner/name — ...` lines under `## cat`."""
    entries: list[dict] = []
    seen: set[str] = set()
    category: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            name = stripped[3:].strip()
            category = None if name.lower() == "summary" else name
            continue
        if stripped.startswith("#") or not stripped.startswith("- "):
            continue
        if category is None:
            continue
        match = DATASET_LINE_RE.match(stripped)
        if not match:
            continue
        repo_id, rest = match.group(1), match.group(2)
        if repo_id in seen:
            continue
        seen.add(repo_id)
        declared = None
        size_match = SIZE_RE.search(rest)
        if size_match:
            declared = int(float(size_match.group(1)) * SIZE_UNITS[size_match.group(2).upper()])
        entries.append({"id": repo_id, "category": category, "declared_bytes": declared})
    return entries


# --------------------------------------------------------------------------
# HuggingFace API metadata
# --------------------------------------------------------------------------
def fetch_metadata(session, repo_id: str, token: str | None) -> dict:
    """GET /api/datasets/<id>; return {status, size, gated}."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = session.get(API_URL.format(repo_id=repo_id), headers=headers, timeout=API_TIMEOUT)
    except Exception as exc:  # network error -> retryable
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "size": None, "gated": False}

    if response.status_code == 404:
        return {"status": "not_found", "size": None, "gated": False}
    if response.status_code in (401, 403):
        return {"status": "unauthorized", "size": None, "gated": True}
    if response.status_code >= 400:
        return {"status": "error", "error": f"HTTP {response.status_code}", "size": None, "gated": False}

    try:
        data = response.json()
    except ValueError as exc:
        return {"status": "error", "error": f"bad JSON: {exc}", "size": None, "gated": False}

    size = data.get("usedStorage")
    if not isinstance(size, int):
        sizes = [f.get("size") for f in (data.get("siblings") or []) if isinstance(f.get("size"), int)]
        size = sum(sizes) if sizes else None
    return {"status": "ok", "size": size, "gated": bool(data.get("gated"))}


# --------------------------------------------------------------------------
# download
# --------------------------------------------------------------------------
def dir_has_files(path: Path) -> bool:
    """True if the directory already holds real (non-cache) files."""
    if not path.is_dir():
        return False
    for child in path.rglob("*"):
        if child.is_file() and ".cache" not in child.parts:
            return True
    return False


def dir_size(path: Path) -> int:
    """Bytes actually on disk under `path`, excluding the HF .cache dir.

    The HF API's ``usedStorage`` overstates the size of the default
    revision (it counts repo storage), so the status file counts what we
    really downloaded instead.
    """
    if not path.is_dir():
        return 0
    return sum(c.stat().st_size for c in path.rglob("*") if c.is_file() and ".cache" not in c.parts)


_DOWNLOAD_SNIPPET = (
    "import sys\n"
    "from huggingface_hub import snapshot_download\n"
    "repo, dest = sys.argv[1], sys.argv[2]\n"
    "snapshot_download(repo_id=repo, repo_type='dataset', local_dir=dest)\n"
)


def snapshot_download_subprocess(repo_id: str, dest: Path, token: str | None, timeout: int) -> None:
    """Run snapshot_download in a child process with a hard timeout."""
    env = dict(os.environ)
    if token:
        env["HF_TOKEN"] = token
    dest.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-c", _DOWNLOAD_SNIPPET, repo_id, str(dest)],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError(tail[-1] if tail else f"exit {proc.returncode}")


def download_with_retries(repo_id: str, dest: Path, token, attempts: int, backoff: float, timeout: int) -> tuple[bool, str, float]:
    """Try snapshot_download up to `attempts` times with exponential backoff."""
    last_error = "unknown error"
    started = time.time()
    for attempt in range(1, attempts + 1):
        try:
            snapshot_download_subprocess(repo_id, dest, token, timeout)
            return True, "", time.time() - started
        except subprocess.TimeoutExpired:
            last_error = f"timeout after {timeout}s"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < attempts:
            time.sleep(backoff * (2 ** (attempt - 1)))
    return False, last_error, time.time() - started


# --------------------------------------------------------------------------
# logging / status
# --------------------------------------------------------------------------
class RunLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("a", encoding="utf-8")

    def write(self, line: str) -> None:
        with _LOG_LOCK:
            self.handle.write(line.rstrip("\n") + "\n")
            self.handle.flush()

    def close(self) -> None:
        self.handle.close()


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------
def build_plan(entries, cfg, overrides):
    """Return (plan, meta) where each plan item is a decided dataset dict."""
    skip_ids = {item.lower() for item in cfg.get_list("Downloader", "skip_ids")}
    skip_gated = cfg.get_bool("Downloader", "skip_gated", True)
    min_bytes = overrides["min_bytes"]
    max_bytes = overrides["max_bytes"]
    allowed_categories = overrides["categories"]
    token_env = cfg.get("Downloader", "hf_token_env", "HF_TOKEN")
    token = os.environ.get(token_env) or None
    workers = overrides["workers"]

    selected = [e for e in entries if not allowed_categories or e["category"] in allowed_categories]
    if overrides["limit"] is not None:
        selected = selected[: overrides["limit"]]

    def annotate(entry):
        item = dict(entry)
        if item["id"].lower() in skip_ids:
            item.update(action="skip", reason="in_skip_ids")
            return item
        meta = fetch_metadata(requests_session, item["id"], token)
        item["meta"] = meta
        item["size"] = meta.get("size")
        if item["size"] is None:
            item["size"] = item.get("declared_bytes")
            item["size_source"] = "source_list"
        else:
            item["size_source"] = "api"
        if meta["status"] == "not_found":
            item.update(action="skip", reason="not_found")
        elif meta["status"] == "unauthorized":
            item.update(action="skip", reason="unauthorized/gated")
        elif meta["status"] == "error":
            item.update(action="skip", reason=f"api_error:{meta.get('error')}")
        elif meta["gated"] and skip_gated:
            item.update(action="skip", reason="gated")
        elif item["size"] is not None and item["size"] > max_bytes:
            item.update(action="skip", reason=f"too_large ({human_bytes(item['size'])})")
        elif item["size"] is not None and item["size"] < min_bytes:
            item.update(action="skip", reason=f"too_small ({human_bytes(item['size'])})")
        else:
            dest = download_root / item["category"] / item["id"].replace("/", "__")
            item["dest"] = dest
            if dir_has_files(dest):
                item.update(action="skip", reason="already_downloaded")
            else:
                item.update(action="download", reason="")
        return item

    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        plan = list(pool.map(annotate, selected))

    meta = {
        "total": len(plan),
        "would_download": sum(1 for i in plan if i["action"] == "download"),
        "would_skip": sum(1 for i in plan if i["action"] == "skip"),
        "categories": sorted({e["category"] for e in entries}),
        "token": bool(token),
    }
    return plan, meta


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="downloader.py",
        description="Download the vetted HuggingFace datasets listed in ReallyHelpfulClean.md.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None,
                        help="Path to config.md (default: ../../config.md relative to this script)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be downloaded, then exit (downloads nothing)")
    parser.add_argument("--category", action="append", default=None,
                        help="Restrict to one category (repeatable)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N datasets in source order")
    parser.add_argument("--max-size", type=float, default=None,
                        help="Override max_size_bytes, in MB")
    parser.add_argument("--min-size", type=float, default=None,
                        help="Override min_size_bytes, in MB")
    parser.add_argument("--workers", type=int, default=None,
                        help="Override downloader workers")
    parser.add_argument("--download-root", default=None,
                        help="Override Datasets.download_root")
    return parser.parse_args(argv)


def resolve_config_path(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates += [DEFAULT_CONFIG, Path.cwd() / "config.md", Path.cwd() / "../../config.md"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit(f"error: could not find config.md (tried {', '.join(str(c) for c in candidates)})")


def main(argv=None) -> int:
    global requests_session, download_root

    args = parse_args(argv)
    config_path = resolve_config_path(args.config)
    cfg = Config(parse_config(config_path), config_path)

    source_list = cfg.path_for("Datasets", "source_list", "datasets/sources/ReallyHelpfulClean.md")
    root_default = cfg.get("Datasets", "download_root", "datasets/downloaded")
    download_root = cfg.path_for("Datasets", "downloaded_root", root_default)
    if args.download_root:
        download_root = Path(args.download_root).expanduser()
    log_file = cfg.path_for("Datasets", "log_file", "datasets/downloaded/_download.log")
    status_file = cfg.path_for("Datasets", "status_file", "datasets/downloaded/_status.json")
    timeout = cfg.get_int("Downloader", "timeout_seconds", 900)
    attempts = cfg.get_int("Downloader", "retry_attempts", 4)
    backoff = cfg.get_float("Downloader", "retry_backoff_seconds", 3)

    if not source_list.is_file():
        raise SystemExit(f"error: source list not found: {source_list}")

    overrides = {
        "categories": args.category or cfg.get_list("Downloader", "categories"),
        "limit": args.limit,
        "workers": args.workers or cfg.get_int("Downloader", "workers", 4),
        "min_bytes": int(args.min_size * SIZE_UNITS["MB"]) if args.min_size is not None
        else cfg.get_int("Downloader", "min_size_bytes", 102400),
        "max_bytes": int(args.max_size * SIZE_UNITS["MB"]) if args.max_size is not None
        else cfg.get_int("Downloader", "max_size_bytes", 524288000),
    }

    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"error: requests is required ({exc})")
    requests_session = requests.Session()

    entries = parse_source_list(source_list)
    print(f"source list : {source_list}")
    print(f"datasets    : {len(entries)} across {len({e['category'] for e in entries})} categories")
    print(f"config      : {config_path}")
    print(f"download root: {download_root}")
    print(f"filters     : min={human_bytes(overrides['min_bytes'])} "
          f"max={human_bytes(overrides['max_bytes'])} "
          f"skip_gated={cfg.get_bool('Downloader', 'skip_gated', True)} "
          f"workers={overrides['workers']}")
    if overrides["categories"]:
        print(f"categories  : {', '.join(overrides['categories'])}")
    print()

    t0 = time.time()
    plan, meta = build_plan(entries, cfg, overrides)
    elapsed = time.time() - t0

    if args.dry_run:
        print(f"{'#':>4}  {'dataset':<48} {'category':<15} {'size':>10}  decision")
        print("-" * 96)
        for index, item in enumerate(plan, 1):
            decision = "DOWNLOAD" if item["action"] == "download" else f"skip: {item['reason']}"
            size = human_bytes(item.get("size"))
            print(f"{index:>4}  {item['id']:<48} {item['category']:<15} {size:>10}  {decision}")
        print("-" * 96)
        print(f"metadata query took {elapsed:.1f}s")
        print(f"would download: {meta['would_download']}")
        print(f"would skip    : {meta['would_skip']}")
        reasons: dict[str, int] = {}
        for item in plan:
            if item["action"] == "skip":
                key = item["reason"].split(" (")[0].split(":")[0]
                reasons[key] = reasons.get(key, 0) + 1
        for key in sorted(reasons):
            print(f"  - {key:<24} {reasons[key]}")
        return 0

    log = RunLog(log_file)
    status = {
        "started_at": now_iso(),
        "finished_at": None,
        "total": len(plan),
        "ok": 0,
        "skipped": 0,
        "failed": 0,
        "bytes": 0,
        "bytes_api_estimate": 0,
        "per_category": {},
    }

    def bump(category: str, field: str) -> None:
        bucket = status["per_category"].setdefault(category, {"ok": 0, "failed": 0})
        bucket[field] += 1

    for item in plan:
        if item["action"] == "skip":
            status["skipped"] += 1
            log.write(f"SKIP {item['id']} {item['reason']}")

    to_download = [item for item in plan if item["action"] == "download"]
    done = 0
    token = os.environ.get(cfg.get("Downloader", "hf_token_env", "HF_TOKEN")) or None

    def worker(item):
        ok, error, seconds = download_with_retries(
            item["id"], item["dest"], token, attempts, backoff, timeout)
        return item, ok, error, seconds

    with cf.ThreadPoolExecutor(max_workers=max(1, overrides["workers"])) as pool:
        for item, ok, error, seconds in pool.map(worker, to_download):
            done += 1
            if ok:
                # Log real on-disk bytes; the API's usedStorage overstates it.
                size = dir_size(item["dest"])
                status["ok"] += 1
                status["bytes"] += size
                status["bytes_api_estimate"] += item.get("size") or 0
                bump(item["category"], "ok")
                log.write(f"OK {item['id']} {size} {seconds:.1f}")
            else:
                status["failed"] += 1
                bump(item["category"], "failed")
                log.write(f"FAIL {item['id']} {error}")
            if done % 10 == 0 or done == len(to_download):
                print(f"progress: {done}/{len(to_download)} "
                      f"(ok={status['ok']} failed={status['failed']})")

    status["finished_at"] = now_iso()
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(status, indent=2), encoding="utf-8")
    log.close()

    print()
    print("=== summary ===")
    print(f"total   : {status['total']}")
    print(f"ok      : {status['ok']}")
    print(f"skipped : {status['skipped']}")
    print(f"failed  : {status['failed']}")
    print(f"bytes   : {status['bytes']} ({human_bytes(status['bytes'])})")
    print(f"log     : {log_file}")
    print(f"status  : {status_file}")
    return 1 if status["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
