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
    assert cfg.path_for("Datasets", "downloaded_root", "x") == PROJECT_ROOT / "datasets/downloaded"


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


FIXTURE_CONFIG = """\
## Project
root: {root}
## Datasets
downloaded_root: dl
## Downloader
skip_gated: true
skip_ids:
  - owner/skipme
min_size_bytes: 100
max_size_bytes: 1000
"""


def _plan(dl, tmp_path, monkeypatch, entries, sizes, gated=None):
    gated = gated or {}
    config_path = tmp_path / "config.md"
    config_path.write_text(FIXTURE_CONFIG.format(root=tmp_path))
    cfg = dl.Config(dl.parse_config(config_path), config_path)

    def fake_fetch(session, repo_id, token):
        return {"status": "ok", "size": sizes.get(repo_id), "gated": gated.get(repo_id, False)}

    monkeypatch.setattr(dl, "fetch_metadata", fake_fetch)
    dl.requests_session = object()
    dl.download_root = tmp_path / "dl"
    overrides = {"categories": [], "limit": None, "workers": 1,
                 "min_bytes": 100, "max_bytes": 1000}
    return dl.build_plan(entries, cfg, overrides)


def test_build_plan_produces_expected_skip_reasons(dl, tmp_path, monkeypatch):
    entries = [{"id": rid, "category": "cat", "declared_bytes": None} for rid in
               ["owner/skipme", "owner/tiny", "owner/huge", "owner/gated", "owner/ok"]]
    sizes = {"owner/skipme": 500, "owner/tiny": 50, "owner/huge": 5000,
             "owner/gated": 500, "owner/ok": 500}
    plan, meta = _plan(dl, tmp_path, monkeypatch, entries, sizes, gated={"owner/gated": True})
    reasons = {item["id"]: item.get("reason") for item in plan}

    assert reasons["owner/skipme"] == "in_skip_ids"
    assert reasons["owner/tiny"].startswith("too_small")
    assert reasons["owner/huge"].startswith("too_large")
    assert reasons["owner/gated"] == "gated"
    assert plan[-1]["action"] == "download"
    assert meta["would_download"] == 1
    assert meta["would_skip"] == 4


def test_build_plan_marks_already_downloaded(dl, tmp_path, monkeypatch):
    entries = [{"id": "owner/ok", "category": "cat", "declared_bytes": None}]
    dest = tmp_path / "dl" / "cat" / "owner__ok"
    dest.mkdir(parents=True)
    (dest / "data.jsonl").write_text("{}\n")
    plan, meta = _plan(dl, tmp_path, monkeypatch, entries, {"owner/ok": 500})

    assert plan[0]["action"] == "skip"
    assert plan[0]["reason"] == "already_downloaded"
    assert meta["would_download"] == 0


def test_build_plan_respects_limit(dl, tmp_path, monkeypatch):
    entries = [{"id": f"owner/d{i}", "category": "cat", "declared_bytes": None} for i in range(5)]
    sizes = {f"owner/d{i}": 500 for i in range(5)}
    config_path = tmp_path / "config.md"
    config_path.write_text(FIXTURE_CONFIG.format(root=tmp_path))
    cfg = dl.Config(dl.parse_config(config_path), config_path)
    monkeypatch.setattr(dl, "fetch_metadata",
                        lambda session, repo_id, token: {"status": "ok", "size": 500, "gated": False})
    dl.requests_session = object()
    dl.download_root = tmp_path / "dl"
    overrides = {"categories": [], "limit": 2, "workers": 1, "min_bytes": 100, "max_bytes": 1000}
    plan, meta = dl.build_plan(entries, cfg, overrides)
    assert len(plan) == 2
