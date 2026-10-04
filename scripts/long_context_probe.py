#!/usr/bin/env python3
"""Measure peak memory for a real forward+backward at a long sequence length.

`training/finetune.py --smoke` uses a short prompt, so it does not exercise
the configured max_length. This probe builds a synthetic conversation of
~N tokens, applies the real chat template with assistant-only labels, and
reports the step time and (via /usr/bin/time -v) the peak RSS.

    ./venv-inference/bin/python scripts/long_context_probe.py --tokens 8192

Always run under a memory cap:
    systemd-run --user --scope -p MemoryMax=12G -- \
        ./venv-inference/bin/python scripts/long_context_probe.py --tokens 8192
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

from orchestrator.chat_template import template_kwargs, tokenize_chat  # noqa: E402
from orchestrator.config import Config  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Long-context memory probe")
    parser.add_argument("--config", default=None)
    parser.add_argument("--tokens", "--length", dest="tokens", type=int, default=8192)
    parser.add_argument("--assistant-repeats", type=int, default=12)
    parser.add_argument("--chunk-size", type=int, default=256)
    parser.add_argument("--loss-mode", choices=["chunked", "standard"], default="chunked")
    parser.add_argument("--dtype", default=None)
    args = parser.parse_args(argv)

    import torch
    import training.finetune as ft

    cfg = Config.load(Path(args.config) if args.config else PROJECT_ROOT / "config.md")
    tokenizer = ft.load_tokenizer(cfg)
    model = ft.build_model(cfg, tokenizer, args.dtype)
    # Match training/finetune.py: the real training path enables gradient
    # checkpointing when config says so, which is what keeps activation
    # memory bounded. Measuring without it is misleading.
    checkpointing = cfg.get_bool("Training", "gradient_checkpointing", True)
    if checkpointing:
        model.gradient_checkpointing_enable()
    model = ft.build_lora(cfg, model, ["q_proj", "v_proj"])
    model.train()
    print(json.dumps({"gradient_checkpointing": checkpointing,
                      "dtype": str(next(model.parameters()).dtype),
                      "loss_mode": args.loss_mode, "chunk_size": args.chunk_size}))

    # Grow the prompt until the rendered conversation reaches ~tokens tokens.
    chunk = "Debug this stack trace, identify the root cause and propose a patch. "
    user = chunk
    messages = [{"role": "user", "content": user},
                {"role": "assistant", "content": "The root cause is a missing symbol. " * args.assistant_repeats}]
    step = chunk * max(1, args.tokens // 400)
    for _ in range(40):
        enc = tokenize_chat(tokenizer, messages, args.tokens, **template_kwargs(False))
        # Stop with the assistant turn still inside the window (the template
        # prefix must not fill the whole context, or masking would be empty).
        if len(enc["input_ids"]) >= args.tokens * 0.85 and enc["assistant_tokens"] > 0:
            break
        user += step
        messages[0]["content"] = user

    print(json.dumps({"probe": "long_context", "requested_tokens": args.tokens,
                      "actual_tokens": len(enc["input_ids"]),
                      "assistant_tokens": enc["assistant_tokens"]}))
    if enc["assistant_tokens"] == 0:
        raise SystemExit("error: assistant span empty (truncated away)")

    batch = {"input_ids": torch.tensor([enc["input_ids"]]),
             "attention_mask": torch.tensor([enc["attention_mask"]]),
             "labels": torch.tensor([enc["labels"]])}
    t = time.time()
    if args.loss_mode == "standard":
        loss = model(**batch).loss
    else:
        loss = ft.compute_chunked_loss(model, batch, args.chunk_size)
    loss.backward()
    print(json.dumps({"loss": round(loss.item(), 4), "step_seconds": round(time.time() - t, 1)}))
    print("LONG_CONTEXT_PROBE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
