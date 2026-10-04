# Data pipeline — Qwen3.5 native chat formatting

## 1. Canonical record schema

```json
{"messages": [{"role": "system"|"user"|"assistant", "content": "..."}]}
```

**Why this shape:** `training/finetune.py` is the consumer, and its contract
is the `messages` list fed straight to the model's chat template:

```python
from orchestrator.chat_template import render, template_kwargs, tokenize_chat
enc = tokenize_chat(tokenizer, example["messages"], max_length, **kwargs)
```

`finetune.py:record_to_messages()` returns `record["messages"]` unchanged for
canonical records, so the formatter's output needs **zero** further
transformation. (Legacy `instruction`/`input`/`output` records are still
accepted as a compatibility path, never produced.)

## 2. Adapter families

The raw download contains many shapes. Each is mapped to canonical messages by
a record-level adapter (`messages_from_record`) or a file-level adapter
(`FILE_MODE`), chosen by keys — not by trusting the dataset label:

| family | how it is detected | datasets |
|---|---|---|
| `chat_messages` (record) | `messages` / `conversations` / `dialog` / `trace` list of `{role, content}` | 66 |
| `conversations` (record) | Topical-Chat `[id, {"content": [{"message","agent"}]}]` array form | 3 |
| `instruction_response` (record) | any of instruction/prompt/question/query/input + output/response/answer/completion/solution (incl. FinQA / NLP-eval / `vars` / AndroidControl field names) | ~55 |
| `csv_qa` (record) | CSV columns incl. `question` + `answers` | PubMedQA |
| `claude_session` (file) | `mondk/agentic-coding-traces`: JSONL of Claude-Code events, keep `type=="message"` | 1 |
| `grouped_conversation` (file) | `HydraLM/...`: rows grouped by `conversation_id`, ordered by `message_id` | 1 |

## 3. Dedup key

`blake2b(16) of json.dumps({"seed", "messages"}, sort_keys=True)` — i.e. an
**exact-match** on the whole normalized record, namespaced by seed.

Deviation from the original design, with evidence: the first implementation
hashed `system + first 64 user chars + first 128 assistant chars`, which
collapsed `beatsprom/autonomous-linux-kernel-ebpf-xdp-suite` from 5,000 raw
records to 20 accepted (4,980 false duplicates, because the records share a
long instruction header). Full-record hashing costs no extra memory (only the
16-byte digest is stored) and yields the correct 2,500 unique records.

## 4. Reject taxonomy

Every rejected record increments exactly one reason:

| reason | meaning |
|---|---|
| `too_short` | total content length < `min_chars` |
| `too_long` | total content length > `max_chars` |
| `empty` | no non-whitespace content in any turn |
| `missing_field` | no user turn *or* no assistant turn |
| `malformed_json` | the source line/file is not valid JSON |
| `unsupported_schema` | no adapter matched the record shape |
| `duplicate` | dedup key already seen in this category |
| `template_mismatch` | reserved for `--verify-template` failures |

Reject counts are recorded per dataset and per category in
`datasets/formatted/<category>/manifest.json` and the top-level `_report.json`.

## 5. Determinism

* Records are written in **dataset order** (sorted by category/dataset path).
* The train/val split is **hash-based**, not shuffle-based:
  `int(digest[:8]) % 1_000_000 < val_fraction * 1_000_000`.
* Consequences: two runs with the same inputs and `--seed` produce
  **byte-identical** `train.jsonl` / `val.jsonl`; the split is
  order-independent and memory-safe (no need to hold 400k+ records in RAM).
* Training-time shuffling is left to the HF `Trainer` (which seeds its own
  sampler), so corpus order does not bias the epoch.

## 6. Template-matching guarantee

The formatter writes **only** `messages`; it never emits `<|im_start|>`,
`<|im_end|>`, `<think>` or `<tool_call>` into content. The tokens come from
`tokenizer.apply_chat_template()`. Guaranteed and verified:

* `--verify-template` renders the first 3 records of every category and
  asserts the token sequence starts with `<|im_start|>` (id 248045), that the
  literal `<|im_start|>` count matches the token count, that no content string
  contains a special token, and that the assistant span is non-empty.
* `tests/test_formatter.py::test_chat_template_roundtrip` enforces the same
  invariant on every test run (this is the guard against the "double special
  tokens" bug).

The empirical template facts (source, token ids, `enable_thinking` behaviour,
and the discovery that `return_assistant_tokens_mask=True` returns an all-zero
mask here) are in `docs/QWEN_CHAT_TEMPLATE.md`.

## 7. Tokenize-and-drop acceptance test

`scripts/tokenize_and_drop_check.py` takes a slice of an output corpus, applies
the real template with assistant-only masking at `config.md` `max_length`, and
reports the truncation rate and mask sanity rate. That is the acceptance test
that the corpus is directly trainable — see the report for the numbers.

### Final `max_length` = 1024 (measured, not guessed)

`scripts/long_context_probe.py` runs one real forward+backward at a given
length with gradient checkpointing enabled (matching `training/finetune.py`),
inside a 12 GiB systemd memory cap:

| sequence length | peak RSS | seconds/step | result |
|---:|---:|---:|---|
| 41 (official `--smoke`) | 5.1 GiB | 4.9 | ok |
| 880 | 9.3 GiB | 116.5 | ok |
| 1804 | 12.4 GiB | 271.0 | ok but thrashing |
| 4096 | — | — | OOM-killed at 12 GiB |
| 6144 | — | — | OOM-killed at 12 GiB |
| 8192 | — | — | OOM-killed at 12 GiB |

The driver is the **fp32 LM head over a 248,320-token vocab**: ~1 GB of logits
plus ~1 GB of gradient per 1024 tokens, on top of 3.2 GiB of fp32 weights.
Attention is not the problem (Qwen3.5-0.8B is hybrid linear-attention with
`max_position_embeddings = 262144`). 1024 is therefore the largest value that
trains without swap thrash on this 14 GiB machine.

### Tokenize-and-drop results at `max_length = 1024` (200 records each)

| category | truncation | all-zero mask | assistant tokens retained | mask sanity |
|---|---:|---:|---:|---:|
| kernel | 100.0% | 0.0% | 0.597 | 100.0% |
| linux | 0.0% | 0.0% | 1.000 | 100.0% |
| cpp | 0.0% | 0.0% | 1.000 | 100.0% |
| python | 0.0% | 0.0% | 1.000 | 100.0% |
| security_data | 0.0% | 0.0% | 1.000 | 100.0% |
| android | 0.0% | 0.0% | 1.000 | 100.0% |
| uncategorized | 9.0% | 1.5% | 0.965 | 98.5% |
| reasoning_algorithms | 4.0% | 2.5% | 0.967 | 97.5% |
| generated_lineageos | 3.0% | 0.0% | 0.998 | 100.0% |
| generated_mql5 | 20.5% | 0.0% | 0.963 | 100.0% |
| agent_tool | 40.0% | 28.0% | 0.661 | 72.0% |
| coding_debug | 98.0% | 97.5% | 0.023 | 2.5% |

Decisions for the three categories above the 20% truncation threshold
(step 3.3): **accept and document, not raise `max_length`** — the probe shows
there is no headroom above 1024 on this machine.

* **kernel (100% truncated, 0% all-zero)** — records have a very long
  `tool_spec` prompt and a long answer; truncation clips the answer tail but
  60% of assistant tokens survive, so the records stay trainable. No action.
* **agent_tool (40% truncated, 28% all-zero)** — ~72% of records train as-is;
  `finetune.py` drops the rest via its all-masked filter and prints the count.
  Documented, not fixed.
* **coding_debug (98% truncated, 97.5% all-zero)** — code traces have
  p50 ≈ 4.9k tokens, so at 1024 the expert would see only ~2.5% of its
  corpus. Do **not** train `debug_review` at 1024. The fix is a long-context
  setup (bf16 weights to halve the base and the logits, and/or a chunked /
  fused cross-entropy so the 248k-vocab logits are never materialised).
  Recorded in `docs/EXPERT_PLAN.md`.

This is a *training* limit, not a data-format limit: the corpora are complete
and correct, and re-running `finetune.py` with a different machine (or the
bf16/chunked-CE change) makes the full corpora usable without reformatting.

## 8. Excluded datasets (not deleted)

`datasets/scripts/format_for_training.py::EXCLUDED_DATASETS` lists 14 datasets
that cannot yield instruction data: retrieval corpora (mteb/cqadupstack-*,
GreenNode/*, CoIR-Retrieval/*), prompt-only or code-only sets
(kirill-vas/*, b-mc2/cli-commands-explained), raw corpora (dumb-dev/cpp-10k),
classification sets (rogue-security/*, ruchit11111/*,
tomhodemon/grounded-visual-spatial-reasoning), a load-test trajectory graph
(zetomatoz/guidellm-*), a doc-chunk set with a sub-500 QA subset
(sg-c/aws_bedrock_documentation_demo), and two datasets with no data files
(mhardalov/reasoning_bg, seablue/DiDi_GAIA_dataset_jsonl). They remain on disk
and are listed in `_report.json` with their reason.
