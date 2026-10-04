"""Unit tests for the dataset downloader's offline parsing logic.

No network calls: these tests only exercise the markdown parser, the
typed config accessors, and the source-list parser.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOWNLOADER = PROJECT_ROOT / "datasets" / "scripts" / "downloader.py"


def _load():
    spec = importlib.util.spec_from_file_location("moe_downloader", DOWNLOADER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["moe_downloader"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dl():
    return _load()


def test_parse_config_sections_and_scalars(dl):
    sections = dl.parse_config(PROJECT_ROOT / "config.md")
    assert sections["Project"]["name"] == "MoE-orchestrator"
    assert sections["Models"]["base_gguf_quant"] == "Q4_K_M"
    assert sections["Downloader"]["timeout_seconds"] == "900"


def test_parse_config_empty_list_literal(dl):
    sections = dl.parse_config(PROJECT_ROOT / "config.md")
    cfg = dl.Config(sections, PROJECT_ROOT / "config.md")
    # `categories: []` must be an empty list, not the string "[]".
    assert cfg.get_list("Downloader", "categories") == []


def test_parse_config_yaml_list(dl):
    sections = dl.parse_config(PROJECT_ROOT / "config.md")
    cfg = dl.Config(sections, PROJECT_ROOT / "config.md")
    assert cfg.get_list("Downloader", "skip_ids") == [
        "bigcode/the-stack-python",
        "codeparrot/codeparrot-clean",
    ]


def test_config_root_relative_paths(dl):
    sections = dl.parse_config(PROJECT_ROOT / "config.md")
    cfg = dl.Config(sections, PROJECT_ROOT / "config.md")
    assert cfg.path_for("Datasets", "download_root", "x") == PROJECT_ROOT / "datasets/downloaded"


def test_source_list_parses_ids_and_categories(dl):
    entries = dl.parse_source_list(PROJECT_ROOT / "datasets/sources/ReallyHelpfulClean.md")
    assert len(entries) > 100
    by_id = {e["id"]: e for e in entries}
    assert by_id["mteb/cqadupstack-android"]["category"] == "android"
    # Declared sizes from the markdown are parsed as a fallback.
    assert by_id["mteb/cqadupstack-android"]["declared_bytes"] == 14784921


def test_source_list_dedupes(dl):
    entries = dl.parse_source_list(PROJECT_ROOT / "datasets/sources/ReallyHelpfulClean.md")
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_human_bytes(dl):
    assert dl.human_bytes(1024) == "1.0 KB"
    assert dl.human_bytes(1048576) == "1.0 MB"
