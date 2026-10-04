# Qwen3.5 chat template — research (ground truth)

Research date: 2026-10-04. Model: `models/Qwen3.5-0.8B` (`model_type: qwen3_5`).
Everything below is empirical output, not assumption.

## 1. Template source

`tokenizer_config.json` **has a `chat_template` key** (7,755 chars). It is
byte-identical to the shipped `chat_template.jinja`:

```
sha256(tokenizer_config chat_template) = 273d8e0e683b8850...
sha256(chat_template.jinja)            = 273d8e0e683b8850...
identical: True
```

Source used by the pipeline: **`tokenizer_config.json` → `chat_template`**
(loaded automatically by `AutoTokenizer`; `tokenizer.chat_template is not None → True`).

## 2. Special token IDs (`added_tokens_decoder`)

| token | id |
|---|---|
| `<|endoftext|>` | 248044 |
| `<|im_start|>` | 248045 |
| `<|im_end|>` | 248046 |

`eos_token = <|im_end|>` (248046), `pad_token = <|endoftext|>` (248044).
**No EOS mismatch**: the chat turn-end token *is* the EOS, so no quirk
workaround is needed. (<think>=248068, </think>=248069, <tool_call>=248058,
<tool_response>=248066, `<|vision_start|>`=248053 etc.)

## 3. Prompt skeletons (verbatim `repr()`)

Single turn, user → assistant, `add_generation_prompt=True`, thinking off (default):

```
'<|im_start|>user\nhi<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
```

Single turn, `enable_thinking=True` (generation prompt):

```
'<|im_start|>user\nhi<|im_end|>\n<|im_start|>assistant\n<think>\n'
```

`enable_thinking=False` is identical to the default (`think == nothink` for
the explicit-False vs no-kwarg case; both emit the *closed empty* think block
`<think>\n\n</think>\n\n`). Only `True` changes the output.

Full turn (user + assistant, `add_generation_prompt=False`):

```
'<|im_start|>user\nhi<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\nhello there<|im_end|>\n'
```

Multi-turn: each turn is `'<|im_start|>' + role + '\n' + content + '<|im_end|>\n'`.
The template inserts the (possibly empty) `<think>...</think>` wrapper **only
for assistant turns after the last user query** (`loop.index0 > last_query_index`);
earlier assistant turns render as bare content. A system message must be first.
Tool calls render as nested `<tool_call><function=NAME><parameter=P>` blocks.

## 4. `return_assistant_tokens_mask` is broken for this template

The template contains **no `{% generation %}` block**, so:

```
[transformers] return_assistant_tokens_mask==True but chat template does not contain `{% generation %}` keyword.
mask: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
mask sum: 0
```

**Fix (implemented in `orchestrator/chat_template.py`)**: compute the
assistant span from the template itself. `render(messages[:-1],
add_generation_prompt=True)` is an exact token prefix of
`render(messages, add_generation_prompt=False)`, so the mask is
`[0]*len(prefix) + [1]*rest`. Verified:

```
len: 26  assistant tokens: 7
decoded assistant span: 'It is 4.<|im_end|>\n'
multiturn assistant span: 'goodbye<|im_end|>\n'
```

## 5. How `training/finetune.py` must consume data

Canonical record (what the formatter writes and finetune.py reads):

```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

Tokenization path: `apply_chat_template(...)` for the text, then
`orchestrator.chat_template.tokenize_chat()` for assistant-only labels at
`max_length` (config.md). A tokenizer-level `truncation=True` is applied on
the combined sequence.

## 6. Mismatches found and fixed

| # | Mismatch | Fix |
|---|---|---|
| 1 | `finetune.py` built a hand-rolled `"### Instruction:\n...### Response:"` fallback string | removed; `apply_chat_template` only, via `orchestrator/chat_template.py` |
| 2 | `finetune.py` expected `instruction`/`input`/`output` records | now expects canonical `{"messages": [...]}` |
| 3 | `finetune.py` used `labels = input_ids` (full-text loss, prompt included) | now assistant-only labels from `assistant_span_mask` |
| 4 | `finetune.py` ignored `enable_thinking` | `--enable-thinking` flag + `[formatted_datasets] enable_thinking` |
| 5 | assumption that `return_assistant_tokens_mask=True` works | it returns all zeros here; replaced with the prefix mask |
| 6 | transformers 4.37.2 (the pinned `venv`) **silently drops the `enable_thinking` template kwarg** — `apply_chat_template(..., enable_thinking=True)` renders identically to `False`. | all template work runs under `venv-inference` (transformers 5.18.0), where the kwarg works; `tests/test_formatter.py::test_enable_thinking_flag_changes_template` skips with an explicit reason on transformers <5 |
