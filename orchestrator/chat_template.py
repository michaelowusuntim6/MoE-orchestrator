"""Qwen3.5 chat-template helpers — the single source of truth.

The model's own template (models/Qwen3.5-0.8B/tokenizer_config.json ->
``chat_template``, identical to ``chat_template.jinja``) is the only thing
allowed to add ``<|im_start|>`` / ``<|im_end|>`` / ``<think>`` tokens. Every
script that tokenizes a conversation goes through here.

Empirical facts (see docs/QWEN_CHAT_TEMPLATE.md):

* Single turn, thinking off:
    <|im_start|>user\\n{user}<|im_end|>\\n
    <|im_start|>assistant\\n<think>\\n\\n</think>\\n\\n{assistant}<|im_end|>\\n
* ``enable_thinking=True`` replaces the closed empty think block with an open
  ``<think>\\n`` (generation prompt) / inserts reasoning before ``</think>``.
* The template has **no** ``{% generation %}`` block, so
  ``return_assistant_tokens_mask=True`` returns an all-zero mask. We therefore
  compute the assistant span from the template itself (prefix method below),
  which is exact because the render is deterministic and prefix-preserving.
"""
from __future__ import annotations

DEFAULT_TEMPLATE_KWARGS = {"enable_thinking": False}

# Special token ids in models/Qwen3.5-0.8B
IM_START_ID = 248045
IM_END_ID = 248046
ENDOFTEXT_ID = 248044
IM_START = "<|im_start|>"
IM_END = "<|im_end|>"


def template_kwargs(enable_thinking: bool | None = None, extra: dict | None = None) -> dict:
    """Build the kwargs passed to apply_chat_template."""
    kwargs = dict(DEFAULT_TEMPLATE_KWARGS)
    if enable_thinking is not None:
        kwargs["enable_thinking"] = bool(enable_thinking)
    if extra:
        kwargs.update(extra)
    return kwargs


def normalize_messages(messages: list) -> list[dict]:
    """Keep only role/content pairs; drop empty turns. Raises ValueError."""
    cleaned = []
    for msg in messages:
        if not isinstance(msg, dict):
            raise ValueError("message must be a dict")
        role = str(msg.get("role", "")).strip().lower()
        content = msg.get("content", "")
        if not isinstance(content, str):
            raise ValueError("message content must be a string")
        content = content.strip()
        if role not in {"system", "user", "assistant", "tool"} or not content:
            raise ValueError(f"invalid or empty message: role={role!r}")
        cleaned.append({"role": role, "content": content})
    return cleaned


def render(tokenizer, messages: list, add_generation_prompt: bool = False, **kwargs) -> str:
    """Render messages with the model's native template. No string surgery."""
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=add_generation_prompt, **kwargs
    )


def _token_ids(tokenizer, text: str) -> list[int]:
    return tokenizer(text, add_special_tokens=False)["input_ids"]


def assistant_span_mask(tokenizer, messages: list, **kwargs) -> tuple[list[int], list[int]]:
    """Return (input_ids, mask) where mask is 1 on the final assistant turn.

    Uses the template's own prefix: render messages[:-1] with
    add_generation_prompt=True, tokenize it, then mark everything the full
    render adds after it. Falls back to a token-id search for the assistant
    header if the prefix is not an exact token prefix.
    """
    full = render(tokenizer, messages, add_generation_prompt=False, **kwargs)
    prefix = render(tokenizer, messages[:-1], add_generation_prompt=True, **kwargs)
    full_ids = _token_ids(tokenizer, full)
    prefix_ids = _token_ids(tokenizer, prefix)

    if full_ids[: len(prefix_ids)] == prefix_ids:
        mask = [0] * len(prefix_ids) + [1] * (len(full_ids) - len(prefix_ids))
        return full_ids, mask

    header = _token_ids(tokenizer, f"{IM_START}assistant\n")
    start = None
    for i in range(len(full_ids) - len(header), -1, -1):
        if full_ids[i:i + len(header)] == header:
            start = i + len(header)
            break
    if start is None:
        raise ValueError("could not locate assistant turn in templated token ids")
    mask = [0] * start + [1] * (len(full_ids) - start)
    return full_ids, mask


def tokenize_chat(tokenizer, messages: list, max_length: int, **kwargs) -> dict:
    """Tokenize a conversation with assistant-only labels (loss masking)."""
    input_ids, mask = assistant_span_mask(tokenizer, messages, **kwargs)
    input_ids = input_ids[:max_length]
    mask = mask[:max_length]
    labels = [tok if m else -100 for tok, m in zip(input_ids, mask)]
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
        "assistant_tokens": sum(mask),
    }
