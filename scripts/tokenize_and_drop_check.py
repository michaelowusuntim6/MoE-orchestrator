#!/usr/bin/env python3
"""Acceptance test: tokenize a slice of a formatted corpus and sanity-check it.

Takes the first N records of datasets/formatted/<category>/train.jsonl, applies
the model's chat template with assistant-only masking at the configured
max_length, and reports:
  * truncation rate (records whose token length exceeds max_length)
  * all-zero-mask rate (no assistant tokens survive truncation)
  * mask sanity (fraction of assistant tokens retained)

    ./venv-inference/bin/python scripts/tokenize_and_drop_check.py --category python
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.chat_template import template_kwargs, tokenize_chat  # noqa: E402
from orchestrator.config import Config  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tokenize-and-drop check")
    parser.add_argument("--config", default=None)
    parser.add_argument("--category", default="python")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--max-length", type=int, default=None)
    parser.add_argument("--enable-thinking", dest="enable_thinking", action="store_true", default=None)
    args = parser.parse_args(argv)

    cfg = Config.load(Path(args.config) if args.config else PROJECT_ROOT / "config.md")
    max_length = args.max_length or cfg.get_int("Training", "max_length", 128)
    enable = args.enable_thinking if args.enable_thinking is not None else cfg.get_bool(
        "Formatted_datasets", "enable_thinking", False)
    kwargs = template_kwargs(enable, None)

    formatted_root = cfg.path_for("Formatted_datasets", "formatted_root", "datasets/formatted")
    path = formatted_root / args.category / "train.jsonl"
    if not path.is_file():
        raise SystemExit(f"error: {path} not found")

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        str(cfg.path_for("Models", "base_hf_path")), trust_remote_code=True)

    total = truncated = all_zero = 0
    retained = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if total >= args.n:
                break
            record = json.loads(line)
            messages = record["messages"]
            # full length before truncation
            from orchestrator.chat_template import assistant_span_mask
            full_ids, full_mask = assistant_span_mask(tokenizer, messages, **kwargs)
            total += 1
            if len(full_ids) > max_length:
                truncated += 1
            enc = tokenize_chat(tokenizer, messages, max_length, **kwargs)
            if enc["assistant_tokens"] == 0:
                all_zero += 1
                retained.append(0.0)
            else:
                denom = max(sum(full_mask), 1)
                retained.append(min(enc["assistant_tokens"] / denom, 1.0))

    print(f"category            : {args.category}")
    print(f"records checked     : {total}")
    print(f"max_length          : {max_length}")
    print(f"enable_thinking     : {enable}")
    print(f"truncation rate     : {100 * truncated / max(total,1):.1f}%  ({truncated}/{total})")
    print(f"all-zero mask rate  : {100 * all_zero / max(total,1):.1f}%  ({all_zero}/{total})")
    print(f"assistant-token retained (mean): {statistics.mean(retained):.3f}")
    print(f"mask sanity rate    : {100 * (1 - all_zero / max(total,1)):.1f}%")
    return 1 if all_zero > total * 0.05 else 0


if __name__ == "__main__":
    sys.exit(main())
