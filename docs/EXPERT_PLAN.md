# Expert plan — Qwen3.5-0.8B LoRA experts

Design carried over: one expert per prompt (no shared expert), manual picker
with IR3DE as highlighter, expert name in the response header. This file
decides only which training corpora to build.

## Experts to train (8)

| expert | sources | records (formatted) | output |
|---|---|---:|---|
| `code_python` | `python` | 151,336 | `training/adapters/code_python` |
| `code_cpp` | `cpp` | 34,131 | `training/adapters/code_cpp` |
| `debug_review` | `coding_debug` | 416,548 | `training/adapters/debug_review` |
| `agent_tool` | `agent_tool` | 676,399 | `training/adapters/agent_tool` |
| `reasoning` | `reasoning_algorithms` | 210,340 | `training/adapters/reasoning` |
| `security` | `security_data` | 170,290 | `training/adapters/security` |
| `android` | `android` | 187,466 | `training/adapters/android` |
| `linux_kernel` | `linux` + `kernel` + `generated_lineageos` | 25,467 | `training/adapters/linux_kernel` |

Rationale:

* **`code_python` / `code_cpp` kept separate** — different languages with
  different idioms; both corpora are large enough (151k / 34k) that merging
  would only blur the expert, and the manual picker makes the distinction
  cheap (the user selects the language, IR3DE highlights when the prompt is
  ambiguous).
* **`debug_review`** is `coding_debug` — trace reading, patch generation and
  review. It overlaps `code_*` conceptually but its data shape
  (stack traces, bug reports, diffs) is distinct enough to justify a corpus.
* **`agent_tool`** is the largest corpus (1.75M raw) and covers function
  calling / agentic coding. It is the natural home for the DeepSeek CLI
  harness's tool-use prompts.
* **`reasoning`** — chain-of-thought and algorithm tasks.
* **`security`** — secure coding, CVEs, AppSec QA.
* **`android`** — Android/LineageOS/Kotlin/device work; the user's primary
  domain, so it gets its own expert even though it is medium-sized.
* **`linux_kernel`** folds three small sources: `linux` (19,740) + `kernel`
  (2,500) + `generated_lineageos` (3,227) = 25,467 records. Shell/CLI, kernel
  and ROM-bring-up questions share a systems-programming register and none is
  large enough alone (kernel is a single dataset).

Optional (not counted in the 8): **`mql5`** from `generated_mql5`
(3,032 records). It has no downloaded corpus and only 3k generated examples —
enough to smoke-test an expert, not enough for a confident one. Kept as
`training/adapters/mql5_optional` if the user wants it.

## Experts deliberately NOT created

* **one per download category** — `uncategorized` (113,960) is a grab bag;
  folding it into another expert would inject noise, so it stays unassigned
  until the router phase.
* **`lineage_device` / `mql5` from downloaded data** — zero datasets exist.
* **retrieval / classification / raw-corpus categories** — see
  `EXCLUDED_DATASETS` in `docs/DATA_PIPELINE.md`; they cannot produce
  instruction pairs.

## Building a combined expert

The formatter writes one corpus per category. For `linux_kernel`, concatenate
in the documented order (train and val separately):

```bash
cd ~/MoE-orchestrator/datasets/formatted
for split in train val; do
  mkdir -p ../formatted_experts/linux_kernel
  cat linux/$split.jsonl kernel/$split.jsonl generated_lineageos/$split.jsonl \
    > ../formatted_experts/linux_kernel/$split.jsonl
done
```

## Size note

Every expert exceeds the 1,000-line minimum by a wide margin (smallest:
`linux_kernel` at 25,467, `code_cpp` at 34,131). One epoch over the full
corpora is far more than a CPU LoRA run needs; use
`training/finetune.py --train --limit N` to cap an individual run.

## Training-memory caveat (`max_length = 1024`)

Measured on this machine (`scripts/long_context_probe.py`, 12 GiB cap,
gradient checkpointing on): 1024 tokens ≈ 9.3 GiB peak / 116 s per step;
2048 ≈ 12.4 GiB and thrashing; 4096+ OOM-killed. `max_length` is therefore
1024 and `finetune.py` drops records whose assistant turn is truncated away.

| expert | usable fraction at 1024 (measured) |
|---|---|
| `linux_kernel`, `code_python`, `code_cpp`, `security`, `android` | ~100% |
| `agent_tool` | ~72% (663k of 676k rows) |
| `reasoning` | ~97.5% |
| **`debug_review` (coding_debug)** | **~2.5% — do not train as-is** |

**`debug_review` is deferred** until either (a) the model is loaded in bf16
to halve the fp32 weights and LM-head logits, or (b) a chunked/fused
cross-entropy removes the 248k-vocab logits materialisation. Both are
training-side changes; the formatted corpus is already complete.
