"""LoFT command-line interface.

Every subcommand returns a non-zero exit code on failure so shell scripts
can detect errors. ``--llama_cpp_dir`` / ``LFT_LLAMA_CPP_DIR`` point at the
llama.cpp checkout instead of the old hardcoded relative path.
"""
import argparse
import os
import sys

import yaml

from loft.train import run_finetune
from loft.export import run_export
from loft.chat import run_chat
from loft.merge import run_merge
from loft.quantize import run_quantize

DEFAULT_LLAMA_CPP_DIR = "../llama.cpp"


def llama_cpp_dir(value=None):
    """Resolve the llama.cpp dir from flag, env var, then default."""
    return value or os.environ.get("LFT_LLAMA_CPP_DIR") or DEFAULT_LLAMA_CPP_DIR


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _resolve_finetune(args):
    """Merge CLI flags over an optional YAML config (e.g. train_config.yaml)."""
    conf = _load_yaml(args.config) if args.config else {}

    def pick(name, default=None):
        value = getattr(args, name, None)
        return value if value is not None else conf.get(name, default)

    model_name = pick("model_name")
    dataset_path = pick("dataset_path")
    output_dir = pick("output_dir")
    if not (model_name and dataset_path and output_dir):
        raise SystemExit(
            "error: finetune needs --model_name, --dataset_path and --output_dir "
            "(on the command line or in a --config file)"
        )
    return {
        "model_name": model_name,
        "dataset_path": dataset_path,
        "output_dir": output_dir,
        "num_train_epochs": pick("num_train_epochs", 1),
        "use_safetensors": bool(pick("use_safetensors", True)),
        "gradient_checkpointing": bool(
            pick("gradient_checkpointing", conf.get("use_gradient_checkpointing", False))
        ),
        "max_length": pick("max_length", 128),
        "per_device_train_batch_size": pick("per_device_train_batch_size", 1),
        "gradient_accumulation_steps": pick("gradient_accumulation_steps", 4),
    }


def build_parser():
    parser = argparse.ArgumentParser(prog="loft", description="Low-RAM Finetuning Toolkit (LoFT)")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    finetune_parser = subparsers.add_parser("finetune", help="Finetune an open-source LLM with LoRA")
    finetune_parser.add_argument("--config", type=str, default=None,
                                 help="YAML defaults file (e.g. train_config.yaml)")
    finetune_parser.add_argument("--model_name", type=str, default=None, help="Hugging Face model ID")
    finetune_parser.add_argument("--dataset_path", type=str, default=None,
                                 help="Path to training dataset (JSON format)")
    finetune_parser.add_argument("--output_dir", type=str, default=None,
                                 help="Directory to save the trained model")
    finetune_parser.add_argument("--num_train_epochs", type=int, default=None,
                                 help="Number of training epochs")
    finetune_parser.add_argument("--max_length", type=int, default=None,
                                 help="Tokenizer max sequence length")
    finetune_parser.add_argument("--use_safetensors", action="store_true", default=None,
                                 help="Use safetensors when loading model")
    finetune_parser.add_argument("--gradient_checkpointing", action="store_true", default=None,
                                 help="Enable gradient checkpointing to reduce memory usage")

    export_parser = subparsers.add_parser("export", help="Export a trained model to GGUF")
    export_parser.add_argument("--model_dir", type=str, required=True, help="Path to trained model directory")
    export_parser.add_argument("--format", type=str, choices=["gguf"], required=True, help="Export format")
    export_parser.add_argument("--output_dir", type=str, required=True, help="Directory to save exported model")
    export_parser.add_argument("--llama_cpp_dir", type=str, default=None,
                               help="Path to the llama.cpp checkout (default: $LFT_LLAMA_CPP_DIR or ../llama.cpp)")

    chat_parser = subparsers.add_parser("chat", help="Run inference with a quantized GGUF model using llama.cpp")
    chat_parser.add_argument("--model_path", type=str, required=True, help="Path to .gguf quantized model")
    chat_parser.add_argument("--prompt", type=str, required=True, help="Prompt text to run")
    chat_parser.add_argument("--n_tokens", type=int, default=128, help="Number of tokens to generate (default: 128)")
    chat_parser.add_argument("--llama_cpp_dir", type=str, default=None, help="Path to the llama.cpp checkout")

    merge_parser = subparsers.add_parser("merge", help="Merge base model with LoRA adapter")
    merge_parser.add_argument("--base_model", type=str, required=True, help="Hugging Face model ID or path")
    merge_parser.add_argument("--adapter_dir", type=str, required=True,
                              help="Path to trained LoRA adapter (output of finetune)")
    merge_parser.add_argument("--output_dir", type=str, required=True, help="Where to save the merged model")

    quantize_parser = subparsers.add_parser("quantize", help="Quantize a GGUF model")
    quantize_parser.add_argument("--model_path", type=str, required=True, help="Path to input .gguf model")
    quantize_parser.add_argument("--output_path", type=str, required=True,
                                 help="Where to save the quantized .gguf model")
    quantize_parser.add_argument("--quant_type", type=str, default="Q4_0",
                                 help="Quantization type (e.g., Q4_0, Q5_1, Q8_0)")
    quantize_parser.add_argument("--llama_cpp_dir", type=str, default=None, help="Path to the llama.cpp checkout")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "finetune":
            run_finetune(**_resolve_finetune(args))
        elif args.command == "export":
            run_export(args.model_dir, args.format, args.output_dir,
                       llama_cpp_dir=llama_cpp_dir(args.llama_cpp_dir))
        elif args.command == "chat":
            run_chat(args.model_path, args.prompt, args.n_tokens,
                     llama_cpp_dir=llama_cpp_dir(args.llama_cpp_dir))
        elif args.command == "merge":
            run_merge(args.base_model, args.adapter_dir, args.output_dir)
        elif args.command == "quantize":
            run_quantize(args.model_path, args.output_path, args.quant_type,
                         llama_cpp_dir=llama_cpp_dir(args.llama_cpp_dir))
    except SystemExit:
        raise
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
