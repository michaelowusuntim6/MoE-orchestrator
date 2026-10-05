"""Tests for the dataset acquisition infrastructure. No network access."""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config, ConfigError, parse_config  # noqa: E402
from scrapers.common import MB, dir_has_files, over_file_limit  # noqa: E402


FIXTURE_CONFIG = """\
## Project
root: {root}

## Scrapers
github_token_env: GITHUB_TOKEN
github_max_file_mb: 500
github_max_repo_mb: 2048
github_clone_depth: 1
github_skip_forks: true
github_skip_archived: false
github_timeout_seconds: 600
github_repos_file: repos.md
github_output_root: github_out
hf_token_env: HF_TOKEN
hf_max_file_mb: 500
hf_max_dataset_mb: 5120
hf_skip_gated: true
hf_dataset_list_file: datasets.md
hf_output_root: hf_out
hf_search_keywords:
  - lineageos
  - mql5
hf_search_max_results: 100
hf_search_min_downloads: 10
lineageos_tree_root: tree
lineageos_max_file_mb: 10
lineageos_output_root: los_out
lineageos_include_extensions:
  - .java
  - .c
lineageos_skip_dirs:
  - .repo
  - out
lineageos_max_files: 1000
download_workers: 2
download_log_file: logs/download.log
download_status_file: logs/status.json

## Upload
hf_upload_repo_prefix: tester
hf_upload_private: false
hf_upload_commit_message_prefix: "v1"
hf_upload_readme_template: README.template.md
"""


@pytest.fixture
def fixture_root(tmp_path):
    (tmp_path / "repos.md").write_text(
        "# repos\n\n## mql5\n# 10 MB\nowner/repo\n", encoding="utf-8")
    (tmp_path / "datasets.md").write_text(
        "# ds\n\n## android\n# 5 MB\nowner/ds\n", encoding="utf-8")
    (tmp_path / "config.md").write_text(FIXTURE_CONFIG.format(root=tmp_path), encoding="utf-8")
    return tmp_path


def load(fixture_root) -> Config:
    return Config.load(fixture_root / "config.md")


# -- config parser ----------------------------------------------------------
def test_config_parser_reads_new_sections(fixture_root):
    cfg = load(fixture_root)
    assert cfg.get_int("Scrapers", "hf_max_file_mb") == 500
    assert cfg.get_str("Scrapers", "github_token_env") == "GITHUB_TOKEN"
    assert cfg.get_bool("Scrapers", "hf_skip_gated") is True
    assert cfg.get_list("Scrapers", "hf_search_keywords") == ["lineageos", "mql5"]
    assert cfg.get_list("Scrapers", "lineageos_skip_dirs") == [".repo", "out"]
    assert cfg.get_str("Upload", "hf_upload_repo_prefix") == "tester"


def test_config_parser_handles_empty_list(tmp_path):
    path = tmp_path / "c.md"
    path.write_text("## Scrapers\nempty: []\nreal:\n  - a\n", encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.get_list("Scrapers", "empty") == []
    assert cfg.get_list("Scrapers", "real") == ["a"]
    sections = parse_config(path)
    assert sections["Scrapers"]["empty"] == []


def test_config_parser_raises_clean_errors(fixture_root):
    cfg = load(fixture_root)
    with pytest.raises(ConfigError, match="missing key 'nope'"):
        cfg.get("Scrapers", "nope")
    with pytest.raises(ConfigError, match="missing section"):
        cfg.get("Nope", "x")


def test_config_paths_resolve_against_root(fixture_root):
    cfg = load(fixture_root)
    assert cfg.path_for("Scrapers", "github_repos_file") == fixture_root / "repos.md"
    assert cfg.get_path("Scrapers", "hf_dataset_list_file") == fixture_root / "datasets.md"


# -- size limits ------------------------------------------------------------
def test_size_limit_enforced():
    limit = 500
    assert over_file_limit(499 * MB, limit) is False
    assert over_file_limit(501 * MB, limit) is True
    assert over_file_limit(2 * 1024 * MB, limit) is True
    # --allow-large bypasses the ceiling
    assert over_file_limit(2 * 1024 * MB, limit, allow_large=True) is False
    # unknown size is never treated as oversized
    assert over_file_limit(None, limit) is False


def test_hf_downloader_applies_guards(tmp_path, monkeypatch):
    sys.path.insert(0, str(PROJECT_ROOT))
    from scrapers.huggingface import hf_downloader as hfd
    cfg = Config.load(_write_config(tmp_path))
    log = hfd.RunLog(tmp_path / "log.txt")
    # gated dataset -> skipped
    monkeypatch.setattr(hfd, "dataset_meta",
                        lambda api, rid, token: (10 * MB, True, 1 * MB, None))
    res = hfd.download_dataset(cfg, "owner/gated", "cat", log, api=object())
    assert (res["action"], res["reason"]) == ("skip", "gated")
    # dataset too large -> skipped
    monkeypatch.setattr(hfd, "dataset_meta",
                        lambda api, rid, token: (9000 * MB, False, 10 * MB, None))
    res = hfd.download_dataset(cfg, "owner/big", "cat", log, api=object())
    assert res["action"] == "skip" and "dataset_too_large" in res["reason"]
    # single file too large -> skipped
    monkeypatch.setattr(hfd, "dataset_meta",
                        lambda api, rid, token: (100 * MB, False, 800 * MB, None))
    res = hfd.download_dataset(cfg, "owner/blob", "cat", log, api=object())
    assert res["action"] == "skip" and "file_too_large" in res["reason"]
    # --allow-large overrides the size ceilings
    res = hfd.download_dataset(cfg, "owner/blob", "cat", log, dry_run=True,
                               allow_large=True, api=object())
    assert res["action"] == "download"
    log.close()


def _write_config(root: Path) -> Path:
    (root / "repos.md").write_text("## mql5\nowner/repo\n", encoding="utf-8")
    (root / "datasets.md").write_text("## android\nowner/ds\n", encoding="utf-8")
    (root / "config.md").write_text(FIXTURE_CONFIG.format(root=root), encoding="utf-8")
    return root / "config.md"


# -- dry runs (no network) --------------------------------------------------
def test_hf_downloader_dry_run(fixture_root, capsys):
    from scrapers.huggingface import hf_downloader as hfd
    code = hfd.main(["--dry-run", "--config", str(fixture_root / "config.md")])
    out = capsys.readouterr().out
    assert code == 0
    assert "dry-run" in out and "owner/ds" in out
    assert not (fixture_root / "hf_out").exists(), "dry run must not download"


def test_github_scraper_dry_run(fixture_root, capsys):
    from scrapers.github import github_scraper as gs
    code = gs.main(["--dry-run", "--config", str(fixture_root / "config.md")])
    out = capsys.readouterr().out
    assert code == 0
    assert "owner/repo" in out and "cloned nothing" in out
    assert not (fixture_root / "github_out").exists()


def test_github_parse_repo_list(tmp_path):
    from scrapers.github import github_scraper as gs
    path = tmp_path / "r.md"
    path.write_text("# t\n\n## mql5\n# size note\nowner/one\n\n## kernel\ntwo/three\n",
                    encoding="utf-8")
    assert gs.parse_repo_list(path) == [("mql5", "owner/one"), ("kernel", "two/three")]


def test_hf_parse_dataset_list(tmp_path):
    from scrapers.huggingface import hf_downloader as hfd
    path = tmp_path / "d.md"
    path.write_text("## android\nowner/one\ncategory: python\nowner/two\n", encoding="utf-8")
    assert hfd.parse_dataset_list(path) == [("android", "owner/one"), ("python", "owner/two")]


# -- lineageos walker -------------------------------------------------------
def test_lineageos_walker_skip_dirs(tmp_path):
    from scrapers.lineageos.lineageos_walker import walk
    root = tmp_path / "tree"
    for rel in ("device/samsung/a04s/A.java", "out/junk/B.java",
                ".repo/x/C.java", "prebuilts/D.java", "system/E.c"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x = 1\n", encoding="utf-8")
    priority, rest, skipped = walk(root, [".java", ".c"], [".repo", "out", "prebuilts"], 10)
    found = {rel for rel, _ in priority + rest}
    assert found == {"device/samsung/a04s/A.java", "system/E.c"}
    assert "device/samsung/a04s/A.java" in {rel for rel, _ in priority}
    assert skipped == 0


def test_lineageos_walker_size_limit(tmp_path):
    from scrapers.lineageos.lineageos_walker import walk
    root = tmp_path / "tree"
    (root / "system").mkdir(parents=True)
    (root / "system" / "small.c").write_text("x\n", encoding="utf-8")
    big = root / "system" / "big.c"
    big.write_bytes(b"0" * (11 * MB))
    _p, _r, skipped = walk(root, [".c"], [], 10)
    assert skipped == 1


def test_lineageos_catalog_written(tmp_path, capsys):
    from scrapers.lineageos import lineageos_walker as lw
    root = _write_config(tmp_path)
    tree = tmp_path / "tree"
    (tree / "device/samsung/a04s").mkdir(parents=True)
    (tree / "device/samsung/a04s" / "BoardConfig.c").write_text("x\n", encoding="utf-8")
    code = lw.main(["--config", str(root), "--sample", "1"])
    assert code == 0
    catalog = json.loads((tmp_path / "los_out" / "_catalog.json").read_text())
    assert catalog["read_only"] is True
    assert catalog["matched_files"] == 1
    assert catalog["files"][0]["sha256"]


# -- uploader ---------------------------------------------------------------
def test_uploader_readme_template(fixture_root, capsys):
    from scrapers.huggingface import hf_uploader as up
    folder = fixture_root / "corpus"
    folder.mkdir()
    (folder / "train.jsonl").write_text('{"messages": []}\n' * 3, encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps({"formatter_version": "qwen35-chat-v1"}),
                                          encoding="utf-8")
    tpl = fixture_root / "README.template.md"
    tpl.write_text("# {name}\nrepo: {repo_id}\nrecords: {records}\n"
                   "license: {license}\nfmt: {formatter_version}\n", encoding="utf-8")
    cfg = load(fixture_root)

    class Args:
        description = None
        source = None
        license = "mit"
        category = "python"

    card = up.render_card(cfg, folder, "tester/code-python", "code-python", Args)
    assert "{name}" not in card and "{repo_id}" not in card
    assert "code-python" in card and "tester/code-python" in card
    assert "records: 3" in card and "fmt: qwen35-chat-v1" in card

    code = up.main(["--config", str(fixture_root / "config.md"), "--name", "code-python",
                    "--path", str(folder), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "dry-run" in out and "huggingface.co/datasets/tester/code-python" in out
    assert not (folder / "README.md").exists(), "dry run must not write the card"


# -- public formatter -------------------------------------------------------
def test_format_public_kernel_vuln_rows():
    from scrapers import format_public as fp
    row = {
        "fixing_commit": "abc123", "introducing_commit": "def456",
        "subsystem": "networking/ipv6", "subsystem_path": "net/ipv6/route.c",
        "bug_type": "crash", "severity_hint": "high", "cve_id": "CVE-2026-0001",
        "lifetime_days": "469", "fix_subject": "ipv6: fix a BUG",
        "fix_author": "A Dev", "files_changed": "2", "insertions": "5",
        "deletions": "1", "keywords": "oops", "related_fixes": "deadbeef",
        "stable_versions": "6.6",
    }
    records = list(fp._kernel_vuln_records_from_rows([row]))
    assert len(records) == 2  # "why vulnerable" + "how fixed"
    for record in records:
        roles = [m["role"] for m in record["messages"]]
        assert roles == ["user", "assistant"]
        assert all("<|im_start|>" not in m["content"] for m in record["messages"])
    assert "def456" in records[0]["messages"][0]["content"]
    assert "CVE-2026-0001" in records[0]["messages"][1]["content"]


def test_format_public_verdict_and_message_shape():
    from scrapers import format_public as fp
    passing = fp.verdict_sentence([{"bucket": "compile-pass", "arm": "frontier",
                                    "ex5_exists": True}])
    failing = fp.verdict_sentence([{"bucket": "compile-fail", "errors": 4}])
    assert "compile-pass" in passing and "errors=0" in passing
    assert "compile-fail" in failing

    record = fp.rec("You are a support expert.", "q", "a")
    assert [m["role"] for m in record["messages"]] == ["system", "user", "assistant"]
    assert set(record) == {"messages"}
