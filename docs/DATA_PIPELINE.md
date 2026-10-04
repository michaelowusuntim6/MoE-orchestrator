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

## 7. Training memory: chunked cross-entropy, dtype, and max_length

### The problem

Qwen3.5-0.8B has a 248,320-token vocabulary. The LM head therefore dominates
memory: at seq_len = 4096 in fp32 the logits tensor alone is ~4 GB, and its
gradient another ~4 GB. That is why the previous session had to drop
`max_length` to 1024 (4096/6144/8192 were all OOM-killed at a 12 GiB cap) and
why `coding_debug` became untrainable.

### The fix (Finding 1 — the load-bearing one)

`orchestrator/chunked_ce.py` implements a `torch.autograd.Function` that never
materialises the full logits:

* forward: chunk the flattened `(tokens, hidden)` activations along the token
  dimension (default 256), project each chunk with `hidden_chunk @ Wᵀ`, compute
  `cross_entropy` for that chunk, accumulate, and **free the chunk**;
* backward: recompute one chunk at a time, form `softmax − onehot`, and
  accumulate only `grad(hidden)` — the LM head is frozen under LoRA, so the
  weight gradient is skipped entirely.

Peak transient cost is one chunk of logits + its fp32 softmax (~380 MB at
chunk 256) regardless of sequence length. Verified numerically identical to
the reference path (`tests/test_chunked_ce.py`: loss equal, max grad diff
2.2e-8).

`training/finetune.py` uses it via a `ChunkedCETrainer` (subclass of
`transformers.Trainer`) that calls the decoder directly and then applies the
chunked loss; `--loss-mode standard` restores the old behaviour for
comparison, and `--chunk-size` controls the chunk.

### Dtype: bf16 rejected on measurement (Finding 2)

bf16 halves the weights (3.2 → 1.6 GiB) and is numerically supported on this
CPU, but it is far slower in backward:

| configuration | 41-token smoke, forward+backward |
|---|---|
| fp32 | **5.1 s** |
| bf16 | 199.7 s (~40× slower) |

Component timing at bf16: decoder forward 7.3 s, chunked CE forward 2.9 s,
**backward 190.7 s**. A micro-benchmark confirms the pattern (512×512 linear
forward: fp32 0.002 s, bf16 0.030 s, fp16 0.085 s). fp16 is worse than bf16,
so `base_hf_dtype: float32` is kept: with the LM head no longer dominating,
the weight memory is affordable and fp32 is ~40× faster.

### Measured ceiling after the fix

`scripts/long_context_probe.py` (fp32, chunked CE, gradient checkpointing on),
each run wrapped in `systemd-run -p MemoryMax=12G`:

| sequence length | peak RSS | s/step | before the fix |
|---:|---:|---:|---|
| 41 (official `--smoke`) | 5.0 GiB | 5.1 | 5.1 GiB |
| 1804 | 7.6 GiB | 210.5 | 12.4 GiB, thrashing |
| 3484 | 10.3 GiB | 433.0 | **OOM-killed** |
| 7124 | 8.8 GiB | 1184.7 | **OOM-killed** |

Every length now completes. `max_length` is therefore **8192** — the largest
value tested. It is a cap, not a fixed cost: the Trainer pads to the longest
sequence in a batch, so short records stay cheap.

### Tokenize-and-drop results at `max_length = 8192` (200 records each)

| category | truncation | all-zero mask | retained | (at 1024) |
|---|---:|---:|---:|---:|
| kernel | 0.0% | 0.0% | 1.000 | 100% truncated |
| linux | 0.0% | 0.0% | 1.000 | 0% |
| cpp | 0.0% | 0.0% | 1.000 | 0% |
| python | 0.0% | 0.0% | 1.000 | 0% |
| security_data | 0.0% | 0.0% | 1.000 | 0% |
| android | 0.0% | 0.0% | 1.000 | 0% |
| uncategorized | 0.0% | 0.0% | 1.000 | 9.0% |
| reasoning_algorithms | 0.0% | 0.0% | 1.000 | 4.0% |
| **coding_debug** | **7.5%** | **7.5%** | **0.925** | 98.0% |
| agent_tool | 0.0% | 0.0% | 1.000 | 40.0% |
| generated_lineageos | 0.0% | 0.0% | 1.000 | 3.0% |
| generated_mql5 | 0.0% | 0.0% | 1.000 | 20.5% |

`coding_debug` — the corpus that made the old limit unusable — is down from
98% truncation to 7.5%, below the 20% threshold. `debug_review` is no longer
blocked.

### Acceptance test

`scripts/tokenize_and_drop_check.py --category <c> --n 200` is the acceptance
test: it applies the real template with assistant-only masking at the
configured `max_length` and reports truncation, all-zero-mask and retention.

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
