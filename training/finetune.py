#!/usr/bin/env python3
"""LoRA fine-tuning entrypoint for Qwen3.5 experts (CPU, transformers 5.x).

Data contract: a JSONL file of canonical records

    {"messages": [{"role": "user", "content": "..."},
                  {"role": "assistant", "content": "..."}]}

Tokenization always goes through the model's own chat template
(``orchestrator.chat_template``); nothing here builds prompt strings by hand.
Loss is assistant-only (the prompt is masked to -100).

LoFT's own finetune path is legacy (transformers 4.37.2 + hardcoded LoRA
hyperparameters); LoFT is kept only for merge/export/quantize/chat.

    ./venv-inference/bin/python training/finetune.py --smoke
    ./venv-inference/bin/python training/finetune.py --train --dataset <file.jsonl> --expert <name>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.chat_template import render, template_kwargs, tokenize_chat  # noqa: E402
from orchestrator.config import Config  # noqa: E402

DEFAULT_CONFIG = PROJECT_ROOT / "config.md"

SMOKE_MESSAGES = [
    {"role": "user", "content": "In one sentence, what is a mixture of experts?"},
    {"role": "assistant",
     "content": "A mixture of experts routes each input to one of several specialized sub-models."},
]


def resolve_config(explicit: str | None) -> Path:
    candidates = [Path(explicit).expanduser()] if explicit else []
    candidates += [DEFAULT_CONFIG, Path.cwd() / "config.md"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit(f"error: config.md not found (tried {[str(c) for c in candidates]})")


def record_to_messages(record: dict) -> list[dict] | None:
    """Canonical `messages`, or a legacy instruction/input/output record."""
    messages = record.get("messages")
    if isinstance(messages, list) and messages:
        return messages
    if "output" in record and ("instruction" in record or "prompt" in record):
        prompt = record.get("instruction") or record.get("prompt") or ""
        extra = record.get("input") or ""
        if extra:
            prompt = f"{prompt}\n\n{extra}"
        return [{"role": "user", "content": prompt},
                {"role": "assistant", "content": record["output"]}]
    return None


def load_examples(path: Path, limit: int | None = None) -> list[dict]:
    rows = []
    text = path.read_text(encoding="utf-8").strip()
    raw = json.loads(text) if text.startswith("[") else [
        json.loads(line) for line in text.splitlines() if line.strip()]
    for record in raw:
        if not isinstance(record, dict):
            continue
        messages = record_to_messages(record)
        if messages:
            rows.append({"messages": messages})
        if limit and len(rows) >= limit:
            break
    return rows


def build_model(cfg: Config, tokenizer):
    import torch
    from transformers import AutoModelForCausalLM

    model_path = cfg.path_for("Models", "base_hf_path")
    dtype_name = str(cfg.get("Models", "base_hf_dtype", "float32")).lower()
    dtype = {"float32": torch.float32, "fp32": torch.float32,
             "float16": torch.float16, "bfloat16": torch.bfloat16}.get(dtype_name, torch.float32)

    model = AutoModelForCausalLM.from_pretrained(
        str(model_path), dtype=dtype, low_cpu_mem_usage=True, trust_remote_code=True)
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


def load_tokenizer(cfg: Config):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        str(cfg.path_for("Models", "base_hf_path")), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def resolve_template_kwargs(cfg: Config, args) -> dict:
    enable = args.enable_thinking
    if enable is None:
        enable = cfg.get_bool("Formatted_datasets", "enable_thinking", False)
    extra = json.loads(args.template_kwargs) if args.template_kwargs else None
    return template_kwargs(enable, extra)


def run_smoke(cfg: Config, args) -> int:
    import time
    import torch

    max_length = cfg.get_int("Training", "max_length", 128)
    kwargs = resolve_template_kwargs(cfg, args)
    tokenizer = load_tokenizer(cfg)
    print(f"loading model from {cfg.path_for('Models', 'base_hf_path')}")

    model = build_model(cfg, tokenizer)
    model = build_lora(cfg, model, args.target_modules)
    model.train()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"LoRA attached: {trainable:,} trainable / {total:,} total "
          f"({100 * trainable / total:.3f}%)")

    print("template:", repr(render(tokenizer, SMOKE_MESSAGES, **kwargs)))
    enc = tokenize_chat(tokenizer, SMOKE_MESSAGES, min(max_length, args.smoke_length), **kwargs)
    print(f"smoke batch: {len(enc['input_ids'])} tokens, "
          f"{enc['assistant_tokens']} assistant (unmasked)")
    if enc["assistant_tokens"] == 0:
        raise SystemExit("error: smoke record produced an all-masked target")

    batch = {
        "input_ids": torch.tensor([enc["input_ids"]]),
        "attention_mask": torch.tensor([enc["attention_mask"]]),
        "labels": torch.tensor([enc["labels"]]),
    }
    t = time.time()
    out = model(**batch)
    out.loss.backward()
    print(f"first forward+backward OK: loss={out.loss.item():.4f} "
          f"step_time={time.time() - t:.1f}s")
    print("SMOKE OK (no optimizer step, nothing saved)")
    return 0


def run_train(cfg: Config, args) -> int:
    from datasets import Dataset
    from transformers import Trainer, TrainingArguments

    if not args.dataset:
        raise SystemExit("error: --train requires --dataset <file.jsonl|file.json>")
    dataset_path = Path(args.dataset).expanduser()
    if not dataset_path.is_file():
        raise SystemExit(f"error: dataset not found: {dataset_path}")

    max_length = cfg.get_int("Training", "max_length", 128)
    kwargs = resolve_template_kwargs(cfg, args)
    tokenizer = load_tokenizer(cfg)
    model = build_model(cfg, tokenizer)
    if cfg.get_bool("Training", "gradient_checkpointing", True):
        model.gradient_checkpointing_enable()
    model = build_lora(cfg, model, args.target_modules)

    rows = load_examples(dataset_path, args.limit)
    print(f"training on {len(rows)} examples from {dataset_path} (max_length={max_length})")

    def to_features(example):
        enc = tokenize_chat(tokenizer, example["messages"], max_length, **kwargs)
        return {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"],
                "labels": enc["labels"]}

    dataset = Dataset.from_list(rows).map(to_features, remove_columns=["messages"])
    before = len(dataset)
    dataset = dataset.filter(lambda row: any(t != -100 for t in row["labels"]))
    if len(dataset) < before:
        print(f"dropped {before - len(dataset)} records with no assistant tokens after truncation")

    output_dir = Path(args.output_dir) if args.output_dir else cfg.path_for("Training", "output_dir")
    adapter_dir = Path(output_dir) / (args.expert or "expert")

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
    Trainer(model=model, args=training_args, train_dataset=dataset).train()
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
    parser.add_argument("--smoke-length", type=int, default=64, help="Token length for --smoke")
    parser.add_argument("--target-modules", nargs="+", default=["q_proj", "v_proj"],
                        help="LoRA target module names")
    parser.add_argument("--enable-thinking", dest="enable_thinking", action="store_true", default=None,
                        help="Pass enable_thinking=True to the chat template")
    parser.add_argument("--template-kwargs", default=None,
                        help="JSON dict of extra apply_chat_template kwargs")
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
