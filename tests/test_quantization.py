"""Tests for the --quantization flag and the quality-gate helpers."""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config  # noqa: E402


@pytest.fixture(scope="module")
def finetune():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "finetune_mod", PROJECT_ROOT / "training" / "finetune.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["finetune_mod"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("choice", ["fp32", "bf16", "8bit", "4bit"])
def test_quantization_flag_is_accepted(finetune, choice):
    args = finetune.parse_args(["--smoke", "--quantization", choice])
    assert args.quantization == choice


def test_quantization_rejects_unknown_value(finetune):
    with pytest.raises(SystemExit):
        finetune.parse_args(["--smoke", "--quantization", "int2"])


def test_default_quantization_comes_from_config(finetune):
    cfg = Config.load(PROJECT_ROOT / "config.md")
    args = finetune.parse_args(["--smoke"])
    assert finetune.resolve_quantization(cfg, args) == cfg.get_str(
        "Quantization", "default_quantization", "fp32")
    assert cfg.get_str("Quantization", "default_quantization") == "fp32"
    assert set(cfg.get_list("Quantization", "quantization_options")) == {
        "fp32", "bf16", "8bit", "4bit"}


def test_cli_overrides_config(finetune):
    cfg = Config.load(PROJECT_ROOT / "config.md")
    args = finetune.parse_args(["--smoke", "--quantization", "8bit"])
    assert finetune.resolve_quantization(cfg, args) == "8bit"


def test_8bit_without_cuda_fails_cleanly(finetune, tmp_path):
    import torch
    if torch.cuda.is_available():
        pytest.skip("CUDA present; this guard only applies on CPU-only hosts")
    cfg = Config.load(PROJECT_ROOT / "config.md")

    class Tok:
        pad_token_id = 0
    with pytest.raises(SystemExit, match="needs bitsandbytes on a CUDA GPU"):
        finetune.build_model(cfg, Tok(), None, "8bit")
