#!/usr/bin/env python3
"""LoRA fine-tuning entrypoint for Qwen3.5 experts (CPU, transformers 5.x).

Why this exists next to LoFT: LoFT pins transformers 4.37.2 (and hardcodes
its LoRA hyperparameters), but the base model is ``model_type: qwen3_5``,
which only transformers 5.x understands. This script is the supported
training path for this project and reads every hyperparameter from
config.md. LoFT stays vendored for the llama.cpp merge/export/quantize/
chat utilities.

Run with the inference venv (transformers 5.x):

    ./venv-inference/bin/python training/finetune.py --smoke
    ./venv-inference/bin/python training/finetune.py --train --dataset <file.jsonl> --expert <name>

``--smoke`` builds the model + LoRA adapter, runs ONE forward/backward pass
on a tiny batch and exits without saving anything. ``--train`` performs
real training; it is never the default.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config  # noqa: E402

DEFAULT_CONFIG = PROJECT_ROOT / "config.md"

SMOKE_INSTRUCTION = "In one sentence, what is a mixture of experts?"
SMOKE_OUTPUT = "A mixture of experts routes each input to one of several specialized sub-models."


def resolve_config(explicit: str | None) -> Path:
    candidates = [Path(explicit).expanduser()] if explicit else []
    candidates += [DEFAULT_CONFIG, Path.cwd() / "config.md"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit(f"error: config.md not found (tried {[str(c) for c in candidates]})")


def format_example(tokenizer, instruction: str, inp: str, output: str) -> str:
    """Render one instruction/response pair using the model chat template."""
    prompt = instruction if not inp else f"{instruction}\n\n{inp}"
    messages = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": output},
    ]
    try:
        return tokenizer.apply_chat_template(messages, tokenize=False)
    except Exception:
        return f"### Instruction:\n{prompt}\n\n### Response:\n{output}"


def build_model(cfg: Config, tokenizer):
    import torch
    from transformers import AutoModelForCausalLM

    model_path = cfg.path_for("Models", "base_hf_path")
    dtype_name = str(cfg.get("Models", "base_hf_dtype", "float32")).lower()
    dtype = {"float32": torch.float32, "fp32": torch.float32,
             "float16": torch.float16, "bfloat16": torch.bfloat16}.get(dtype_name, torch.float32)

    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        dtype=dtype,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    model.config.use_cache = False  # required when gradient checkpointing is on
    if tokenizer.pad_token_id is not None:
        model.config.pad_token_id = tokenizer.pad_token_id
    return model


def build_lora(cfg: Config, model, target_modules):
    from peft import LoraConfig, TaskType, get_peft_model

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        inference_mode=False,
        r=cfg.get_int("Training", "lora_r", 8),
        lora_alpha=cfg.get_int("Training", "lora_alpha", 16),
        lora_dropout=cfg.get_float("Training", "lora_dropout", 0.1),
        target_modules=target_modules,
    )
    return get_peft_model(model, lora_config)


def encode(tokenizer, text: str, max_length: int):
    return tokenizer(text, truncation=True, max_length=max_length, return_tensors="pt")


def run_smoke(cfg: Config, args) -> int:
    import torch
    from transformers import AutoTokenizer

    max_length = cfg.get_int("Training", "max_length", 128)
    seq_len = min(max_length, args.smoke_length)

    model_path = cfg.path_for("Models", "base_hf_path")
    print(f"loading tokenizer + model from {model_path} (this takes a moment on CPU)")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = build_model(cfg, tokenizer)
    model = build_lora(cfg, model, args.target_modules)
    model.train()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"LoRA attached: {trainable:,} trainable / {total:,} total params "
          f"({100 * trainable / total:.3f}%)")

    text = format_example(tokenizer, SMOKE_INSTRUCTION, "", SMOKE_OUTPUT)
    batch = encode(tokenizer, text, seq_len)
    batch["labels"] = batch["input_ids"].clone()
    print(f"smoke batch: {batch['input_ids'].shape[1]} tokens")

    t = time.time()
    out = model(**batch)
    loss = out.loss
    loss.backward()
    step_time = time.time() - t
    print(f"first forward+backward OK: loss={loss.item():.4f} step_time={step_time:.1f}s")
    print("SMOKE OK (no optimizer step, nothing saved)")
    return 0


def load_examples(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("["):
        rows = json.loads(text)
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return [r for r in rows if isinstance(r, dict) and "output" in r]


def run_train(cfg: Config, args) -> int:
    import torch
    from datasets import Dataset
    from transformers import AutoTokenizer, Trainer, TrainingArguments

    if not args.dataset:
        raise SystemExit("error: --train requires --dataset <file.jsonl|file.json>")
    dataset_path = Path(args.dataset).expanduser()
    if not dataset_path.is_file():
        raise SystemExit(f"error: dataset not found: {dataset_path}")

    max_length = cfg.get_int("Training", "max_length", 128)
    model_path = cfg.path_for("Models", "base_hf_path")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = build_model(cfg, tokenizer)
    if cfg.get_bool("Training", "gradient_checkpointing", True):
        model.gradient_checkpointing_enable()
    model = build_lora(cfg, model, args.target_modules)

    rows = load_examples(dataset_path)
    if args.limit:
        rows = rows[: args.limit]
    print(f"training on {len(rows)} examples from {dataset_path}")

    def to_features(example):
        text = format_example(tokenizer, example.get("instruction", ""),
                              example.get("input", ""), example["output"])
        enc = tokenizer(text, truncation=True, max_length=max_length)
        enc["labels"] = list(enc["input_ids"])
        return enc

    dataset = Dataset.from_list(rows).map(to_features, remove_columns=list(rows[0].keys()))

    output_dir = Path(args.output_dir) if args.output_dir else cfg.path_for("Training", "output_dir")
    expert = args.expert or "expert"
    adapter_dir = Path(output_dir) / expert

    training_args = TrainingArguments(
        output_dir=str(adapter_dir),
        per_device_train_batch_size=cfg.get_int("Training", "batch_size", 1),
        gradient_accumulation_steps=cfg.get_int("Training", "grad_accumulation", 4),
        num_train_epochs=cfg.get_int("Training", "num_train_epochs", 1),
        learning_rate=cfg.get_float("Training", "learning_rate", 2e-4),
        save_strategy=cfg.get("Training", "save_strategy", "epoch"),
        save_total_limit=cfg.get_int("Training", "save_total_limit", 1),
        logging_steps=1,
        report_to="none",
        remove_unused_columns=False,
        gradient_checkpointing=cfg.get_bool("Training", "gradient_checkpointing", True),
    )
    trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
    trainer.train()
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    print(f"adapter saved to {adapter_dir}")
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="finetune.py",
        description="LoRA fine-tuning for Qwen3.5 experts (CPU, transformers 5.x).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None, help="Path to config.md")
    parser.add_argument("--smoke", action="store_true",
                        help="Build model+LoRA and run one forward/backward pass, then exit")
    parser.add_argument("--train", action="store_true", help="Run real LoRA training")
    parser.add_argument("--dataset", default=None, help="Training file (.jsonl or .json)")
    parser.add_argument("--expert", default=None, help="Expert name (adapter subdirectory)")
    parser.add_argument("--output-dir", default=None, help="Override Training.output_dir")
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N examples")
    parser.add_argument("--smoke-length", type=int, default=32, help="Token length for --smoke")
    parser.add_argument("--target-modules", nargs="+", default=["q_proj", "v_proj"],
                        help="LoRA target module names")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = Config.load(resolve_config(args.config))
    if args.smoke:
        return run_smoke(cfg, args)
    if args.train:
        return run_train(cfg, args)
    print("nothing to do: pass --smoke (verify the path) or --train (real training)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
