"""Shared helpers for every scraper: config, size limits, logging, status.

One config.md is the single source of truth. Every scraper reads its
tunables through :func:`load_config` and enforces the same 500 MB
per-file ceiling through :func:`over_file_limit`.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config, ConfigError  # noqa: E402

DEFAULT_CONFIG = PROJECT_ROOT / "config.md"
MB = 1024 * 1024


def load_config(path: str | Path | None = None) -> Config:
    """Load config.md (the only config file in the project)."""
    cfg_path = Path(path).expanduser() if path else DEFAULT_CONFIG
    if not cfg_path.is_file():
        raise SystemExit(f"error: config.md not found at {cfg_path}")
    return Config.load(cfg_path)


def human_bytes(n) -> str:
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def dir_has_files(path: Path) -> bool:
    """True if the directory already holds real (non-cache) files."""
    if not path.is_dir():
        return False
    for child in path.rglob("*"):
        if child.is_file() and ".cache" not in child.parts:
            return True
    return False


def dir_size(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(c.stat().st_size for c in path.rglob("*")
               if c.is_file() and ".cache" not in c.parts)


def over_file_limit(size_bytes: int | None, limit_mb: int, allow_large: bool = False) -> bool:
    """The one place the 500 MB per-file rule is applied."""
    if allow_large or size_bytes is None:
        return False
    return size_bytes > int(limit_mb) * MB


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class RunLog:
    """Append-only log with an explicit flush on every line."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._handle = self.path.open("a", encoding="utf-8")

    def write(self, line: str) -> None:
        with self._lock:
            self._handle.write(line.rstrip("\n") + "\n")
            self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def write_status(path: Path, started_at: str, counters: dict, extra: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"started_at": started_at, "finished_at": now_iso()}
    payload.update(counters)
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def print_summary(title: str, counters: dict) -> None:
    print(f"\n=== {title} ===")
    for key in ("total", "ok", "skipped", "failed", "bytes"):
        if key in counters:
            value = human_bytes(counters[key]) if key == "bytes" else counters[key]
            print(f"{key:9}: {value}")
