"""Tests for the shared config.md parser (orchestrator/config.py)."""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config, ConfigError, parse_config  # noqa: E402

FIXTURE = """\
# comment
## Project

root: {root}

## Downloader

workers: 4
ratio: 0.5
skip_gated: true
categories: []
skip_ids:
  - a/b
  - c/d
other_list:
  - x

## Training

lora_r: 8
"""


@pytest.fixture
def cfg(tmp_path):
    path = tmp_path / "config.md"
    path.write_text(FIXTURE.format(root=tmp_path))
    return Config.load(path)


def test_empty_list_literal_parses_to_empty_list(cfg):
    assert cfg.get_list("Downloader", "categories") == []


def test_yaml_lists_and_adjacent_lists(cfg):
    assert cfg.get_list("Downloader", "skip_ids") == ["a/b", "c/d"]
    # a second list key in the same section must not absorb the first's items
    assert cfg.get_list("Downloader", "other_list") == ["x"]


def test_scalar_types(cfg):
    assert cfg.get_int("Downloader", "workers") == 4
    assert cfg.get_float("Downloader", "ratio") == 0.5
    assert cfg.get_bool("Downloader", "skip_gated") is True
    assert cfg.get_int("Training", "lora_r") == 8


def test_missing_key_raises_clean_error(cfg):
    with pytest.raises(ConfigError, match="missing key 'nope'"):
        cfg.get("Downloader", "nope")


def test_missing_section_raises_clean_error(cfg):
    with pytest.raises(ConfigError, match="missing section \\[Router\\]"):
        cfg.get("Router", "router_type")


def test_default_suppresses_error(cfg):
    assert cfg.get("Downloader", "nope", default="fallback") == "fallback"


def test_path_for_returns_path_relative_to_root(cfg, tmp_path):
    result = cfg.path_for("Project", "root")
    assert isinstance(result, Path)
    assert result == tmp_path


def test_path_for_expands_tilde(tmp_path):
    path = tmp_path / "config.md"
    path.write_text("## Project\nroot: " + str(tmp_path) + "\n## X\np: ~/data\n")
    cfg = Config.load(path)
    assert cfg.path_for("X", "p") == Path.home() / "data"


def test_path_for_missing_key_raises(cfg):
    with pytest.raises(ConfigError):
        cfg.path_for("Downloader", "nope")
