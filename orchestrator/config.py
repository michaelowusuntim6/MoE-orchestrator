"""Shared parser for ``config.md`` — the single source of truth.

Format:

    ## Section
    key: value
    list_key:
      - item one
      - item two
    empty_list: []

Used by ``datasets/scripts/downloader.py`` and ``training/finetune.py`` so
every script reads the same tunables the same way.
"""
from __future__ import annotations

from pathlib import Path


class ConfigError(KeyError):
    """Raised when a required section/key is missing from config.md."""


# Sentinel so a real default of ``None`` is distinguishable from "no default".
_MISSING = object()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_config(path: Path) -> dict:
    """Parse ``## Section`` headers and ``key: value`` lines into a dict.

    A key with an empty value (or the literal ``[]``) opens a YAML-style
    list; following ``- item`` lines are appended to it. ``###`` sub-headers
    and ``#`` comments are ignored.
    """
    path = Path(path)
    sections: dict[str, dict] = {}
    current: dict | None = None
    list_key: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            continue
        if stripped.startswith("## "):
            name = stripped[3:].strip()
            current = sections.setdefault(name, {})
            list_key = None
            continue
        if stripped.startswith("#"):
            continue
        if current is None:
            continue
        if stripped.startswith("- "):
            if list_key is not None:
                current[list_key].append(_strip_quotes(stripped[2:].strip()))
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if value in ("", "[]"):
            current[key] = []
            list_key = key
        else:
            current[key] = _strip_quotes(value)
            list_key = None
    return sections


class Config:
    """Typed accessors over parsed config.md with root-relative paths.

    Required keys raise :class:`ConfigError` when missing; pass a
    ``default`` to opt out of that.
    """

    def __init__(self, sections: dict, config_path: Path | str | None = None):
        self.sections = sections
        self.path = Path(config_path) if config_path is not None else None
        root = self.get("Project", "root", default=None)
        self.root = Path(str(root)).expanduser() if root else Path.cwd()

    @classmethod
    def load(cls, path: Path | str) -> "Config":
        path = Path(path)
        return cls(parse_config(path), path)

    # -- scalar access ---------------------------------------------------
    def get(self, section: str, key: str, default=_MISSING):
        if section not in self.sections:
            if default is _MISSING:
                raise ConfigError(f"missing section [{section}] in {self.path}")
            return default
        if key not in self.sections[section]:
            if default is _MISSING:
                raise ConfigError(f"missing key '{key}' in section [{section}] of {self.path}")
            return default
        return self.sections[section][key]

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        try:
            return int(float(self.get(section, key, default)))
        except (TypeError, ValueError):
            return default

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(section, key, default))
        except (TypeError, ValueError):
            return default

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        value = self.get(section, key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def get_list(self, section: str, key: str, default=_MISSING) -> list:
        value = self.get(section, key, [] if default is _MISSING else default)
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [item.strip() for item in str(value).split(",") if item.strip()]

    # -- paths -----------------------------------------------------------
    def path_for(self, section: str, key: str, default=_MISSING) -> Path:
        """Resolve a config value to a Path relative to the project root."""
        raw = self.get(section, key, default)
        candidate = Path(str(raw)).expanduser()
        return candidate if candidate.is_absolute() else (self.root / candidate)
