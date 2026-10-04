"""Offline tests for the LoFT CLI and data files."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "loft.cli", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_help_exits_zero():
    assert run_cli("--help").returncode == 0


def test_export_rejects_onnx():
    assert "onnx" not in run_cli("export", "--help").stdout


def test_llama_cpp_dir_flag_and_env(monkeypatch):
    sys.path.insert(0, str(ROOT))
    from loft.cli import llama_cpp_dir
    monkeypatch.setenv("LFT_LLAMA_CPP_DIR", "/tmp/llama-env")
    assert llama_cpp_dir() == "/tmp/llama-env"
    assert llama_cpp_dir("/tmp/explicit") == "/tmp/explicit"


def test_sample_dataset_is_valid_json():
    rows = json.loads((ROOT / "data" / "sample_finetune_data.json").read_text())
    assert isinstance(rows, list) and len(rows) == 2
    for row in rows:
        assert {"instruction", "input", "output"} <= set(row)


def test_train_config_yaml_is_used(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("model_name: foo\ndataset_path: bar\noutput_dir: baz\nmax_length: 64\n")
    sys.path.insert(0, str(ROOT))
    from loft.cli import _load_yaml, build_parser, _resolve_finetune
    args = build_parser().parse_args(["finetune", "--config", str(config)])
    resolved = _resolve_finetune(args)
    assert resolved["model_name"] == "foo"
    assert resolved["max_length"] == 64
