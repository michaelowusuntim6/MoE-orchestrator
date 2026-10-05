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

## Training memory: resolved (`max_length = 8192`)

The previous limit of 1024 was caused by the fp32 LM head over a 248,320-token
vocab. `orchestrator/chunked_ce.py` now computes the loss one chunk at a time
(the LM-head logits are never fully materialised), so the ceiling moved:

| sequence length | peak RSS | before |
|---:|---:|---|
| 1804 | 7.6 GiB | 12.4 GiB, thrashing |
| 3484 | 10.3 GiB | OOM-killed |
| 7124 | 8.8 GiB | OOM-killed |

bf16 was rejected on measurement (CPU backward 199.7 s vs 5.1 s for fp32 at 41
tokens), so weights stay fp32. Details in `docs/DATA_PIPELINE.md` §7.

| expert | usable fraction at 8192 (measured) |
|---|---|
| `linux_kernel`, `code_python`, `code_cpp`, `security`, `android`, `reasoning`, `agent_tool`, `mql5_optional` | 100% |
| **`debug_review` (coding_debug)** | **92.5%** (7.5% truncated, was 2.5%) |

**`debug_review` is unblocked.** Note the cost is wall-clock, not memory: a
full-length (8k-token) step takes ~20 minutes on this CPU, so cap runs with
`--limit` and prefer shorter records while iterating.

## Public-corpus additions (2026-10-05 campaign)

Nine new formatted categories add **615,330 records**. Mapping to experts:

| expert | new corpora | added records |
|---|---|---:|
| `android` | `supportbench_lineageos` (4,741) + `lineageos_tree` (194,832) | 199,573 |
| `linux_kernel` | `kernel_vuln` (241,116) + `kernel_vuln_full_sample` (100,506) + `kernel_syzfix_sample` (1,918) | 343,540 |
| `security` | `security_qa` (22,953) | 22,953 |
| `code_python` | `python_codeparrot_sample` (48,023) | 48,023 |
| `mql5_optional` | `mql5_repos` (1,057) + `mql5_benchmark` (184) | 1,241 |

Consequences:

* **`linux_kernel` is now a first-class expert**, not a folded-in side source:
  343,540 real kernel vulnerability records (bug types, CVE ids, lifetimes,
  commit subjects and real patch diffs from syzfix).
* **`mql5_optional` is now viable**: 1,241 records of real MQL5 source
  (359 `.mq5` + 1,077 `.mqh` files across four repositories) plus the
  benchmark prompts and their compile verdicts.
* **`android` gains 199,573 records** of real LineageOS framework, device and
  sepolicy source, ordered device-first (A04s / Exynos850).
* The 4 kernel GitHub repos remain deliberately excluded; kernel source comes
  from the local tree walk and the vulnerability datasets.

All nine new categories pass `--verify-template` and measure ≤2.5% truncation
with 0% all-zero masks at `max_length = 8192`.

## Expansion gains (later 2026-10-05 session)

Nine more categories add **383,047 records**:

| expert | new corpora | added records |
|---|---|---:|
| `linux_kernel` | `linux_kernel_commits` (37,770) + `linux_kernel_assembly` (4,203) + `linux_kernel_ioctl` (1,289) + `kernel_davinci` (5,498, GPU-only) | 48,760 |
| `debug_review` | `code_review` (233,235) | 233,235 |
| `security` | `security_expanded` (8,480) | 8,480 |
| `android` | `android_malware` (7,489) | 7,489 |
| `mql5_optional` | `mql5_expanded` (1,656) + `forex_calendar` (83,427) | 85,083 |

The MQL5 expert is no longer marginal: with `mql5_repos`, `mql5_benchmark`,
`mql5_expanded` and `forex_calendar` it now has **86,324 records**, so it can
graduate from `mql5_optional` to a full expert. `debug_review` doubles in size
(333,343 with `coding_debug` + `code_review`).

`kernel_davinci` is excluded from the laptop training plan: 100% of its
records truncate at `max_length = 8192`. Train it on a GPU with a larger
context and 8-bit weights (`docs/TRAINING_RUNBOOK.md`).

## Published HF corpora per expert

All 30 corpora are live under `michaelowusuntim6`; full links in
`docs/HF_UPLOAD_GUIDE.md`.

| expert | HF repos | notes |
|---|---|---|
| `android` | `android-qwen35`, `lineageos-tree-qwen35`, `lineageos-support-qwen35`, `lineageos-generated-qwen35` | full (+ 185k source-tree records) |
| `linux_kernel` | `kernel-qwen35`, `linux-qwen35`, `kernel-vuln-qwen35`, `kernel-syzfix-qwen35` (sample), `kernel-vuln-full-qwen35` (sample), `linux-kernel-commits-qwen35`, `linux-kernel-asm-qwen35`, `linux-kernel-ioctl-qwen35`, `kernel-davinci-qwen35` | two are 500 MB samples; `kernel-davinci-qwen35` **needs GPU** |
| `mql5_optional` → `mql5` | `mql5-repos-qwen35`, `mql5-expanded-qwen35`, `mql5-generated-qwen35`, `forex-calendar-qwen35`, `mql5-compile-benchmark` | the last is an **eval set**, not training data |
| `code_python` | `python-qwen35`, `python-codeparrot-qwen35` | the second is a 500 MB sample |
| `code_cpp` | `cpp-qwen35` | full |
| `debug_review` | `debug-qwen35`, `code-review-qwen35` | full |
| `security` | `security-qwen35`, `security-qa-qwen35`, `security-expanded-qwen35`, `android-malware-qwen35` | full |
| `agent_tool` / `reasoning` | `agent-tool-qwen35`, `reasoning-qwen35` | full |
| unassigned | `uncategorized-qwen35` | grab bag, router/mixing only |

Sampled corpora (500 MB streamed) are marked above; everything else is the
complete formatted set.
