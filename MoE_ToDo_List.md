# MoE Orchestrator — master TODO list

Last updated: 2026-10-04T21:40:00Z
Current phase: 2 (data formatted for training; expert plan written)
Last completed step: 1.5.9 tokenize-and-drop verified for all 12 corpora

## Phase 0 — Scaffold
- [x] 0.1 Create ~/MoE-orchestrator/ and subfolders
- [x] 0.2 Copy base HF model into models/
- [x] 0.3 Copy base GGUF into models/
- [x] 0.4 Copy generated datasets into datasets/generated/
- [x] 0.5 Clone LoFT fresh from upstream (vendored at 32fa65a, see LoFT/UPSTREAM.md)
- [x] 0.6 Create Python 3.11 venv and install dependencies
- [x] 0.7 Write config.md
- [x] 0.8 Write datasets/scripts/downloader.py
- [x] 0.9 Run downloader.py --dry-run
- [x] 0.10 Write README.md
- [x] 0.11 git init and initial commit

## Phase 1 — Dataset download
- [x] 1.1 Decide which categories to download (`categories: []` = all)
- [x] 1.2 Run downloader.py for real — 143 ok / 49 skipped / 0 failed
- [x] 1.3 Verify each category has at least 3 datasets
      BLOCKER: `kernel` has 1 dataset (5,000 records); `lineage_device` and
      `mql5` have 0. The source list itself marks these "Categories needing
      more data". Plan: for a kernel expert, supplement with
      datasets/generated/ (lineageos) or add more sources; skip mql5 until
      data exists. Do not train an expert on kernel/mql5 yet.
- [x] 1.4 Build a manifest of downloaded datasets — `datasets/downloaded/_manifest.md`

## Phase 2 — Expert selection
- [x] 2.1 Group downloaded datasets by expert category (in `_manifest.md`)
- [x] 2.2 Decide how many experts to train — 8 + 1 optional (see `docs/EXPERT_PLAN.md`)
- [x] 2.3 Write the expert plan — `docs/EXPERT_PLAN.md`

## Phase 1.5 — Format datasets for training
- [x] 1.5.1 Research the Qwen3.5 chat template (docs/QWEN_CHAT_TEMPLATE.md)
- [x] 1.5.2 Edit every data/tokenization .py file to use apply_chat_template
- [x] 1.5.3 Survey every dataset's record shape (datasets/downloaded/_format_survey.json)
- [x] 1.5.4 Design the canonical record schema (docs/DATA_PIPELINE.md)
- [x] 1.5.5 Write datasets/scripts/format_for_training.py
- [x] 1.5.6 Dry-run passes
- [x] 1.5.7 Real run per category — 12 corpora written
- [x] 1.5.8 Template verification passes for all 12 categories
- [x] 1.5.9 Tokenize-and-drop verified at max_length=1024 (docs/DATA_PIPELINE.md §7)

## Phase 3 — Fine-tune experts
- [ ] 3.1 Fine-tune the first expert with `training/finetune.py`
- [ ] 3.2 Verify the LoRA adapter
- [ ] 3.3 Convert to GGUF (LoFT `export`, or llama.cpp `convert_lora_to_gguf.py`)
- [ ] 3.4 Serve with llama.cpp and test inference

## Phase 4 — Router (IR3DE)
- [ ] 4.1 Read the IR3DE paper
- [ ] 4.2 Implement the router
- [ ] 4.3 Test routing against the expert set

## Phase 5 — CLI integration
- [ ] 5.1 Add a provider to the DeepSeek CLI harness that routes to the selected expert
- [ ] 5.2 Add the manual expert picker
- [ ] 5.3 Add the expert name to the response header

## Phase 6 — MoE composition
- [ ] 6.1 Decide composition strategy (MergeKit vs router + multiple servers)
- [ ] 6.2 Implement composition
- [ ] 6.3 Benchmark the MoE

## Decisions (2026-10-04 audit session)

### B.1 — transformers blocker → Option 2 (custom training entrypoint)
Qwen3.5 is `model_type: qwen3_5`; transformers 4.37.2 raises
`ValueError: ... model type 'qwen3_5' but Transformers does not recognize
this architecture`. Confirmed with the pinned `venv` (see verification).

Chosen: keep the pinned `venv` for LoFT (unchanged, still passes the
import check) and add `venv-inference` (transformers 5.18.0, torch
2.14.1+cpu, peft 0.21.2). Training entrypoint is
`training/finetune.py`, which reads config.md for every hyperparameter.
LoFT's own `finetune` path is legacy (pinned to 4.37.2 + hardcoded LoRA
hyperparameters); LoFT stays vendored for merge/export/quantize/chat.

Verified: `--smoke` runs one forward+backward on Qwen3.5 + LoRA
(319,488 trainable / 752,712,512 params = 0.042%), loss 2.5217.

Exact next command:

    ./venv-inference/bin/python training/finetune.py --smoke

### B.2 — LoFT: fixed in place (14 bugs)
All 12 audited bugs plus two extras (dead `elif` in export.py; swallowed
subprocess failures) are fixed. See `docs/LoFT_KNOWN_BUGS.md`. New tests:
`LoFT/tests/test_cli.py` (5 passing).

### B.3 — LoFT stays vendored (no submodule)
The nested `.git` was removed in the previous session so the parent commit
contains LoFT's sources. Upstream tracking is manual and documented in
`LoFT/UPSTREAM.md`. Re-syncing = clone upstream and diff.

## Progress log

[20:10:00] Step 0 research: Qwen3.5 template found in tokenizer_config.json (identical to chat_template.jinja); ids im_start=248045 im_end=248046 endoftext=248044; eos == <|im_end|> (no quirk)
[20:12:00] Found return_assistant_tokens_mask=True returns an ALL-ZERO mask (template has no {% generation %}); implemented orchestrator/chat_template.py assistant_span_mask (prefix method) instead
[20:20:00] Rewrote training/finetune.py to the canonical {"messages":[...]} schema with apply_chat_template + assistant-only labels; no hand-rolled prompts
[20:24:00] Surveyed 143 datasets: chat_messages=66, instruction_response=46, unknown=13, text_only=8, tool_calls=4, classification=3, no_data=2, code_only=1
[20:30:00] Reclassified all 13 unknowns by inspecting 10 records each (agent session logs, Tau2 traces, Topical-Chat arrays, HydraLM grouped rows, FinQA/NLP-eval/Rowden/AndroidControl field names); 14 datasets documented as excluded
[20:35:00] Wrote datasets/scripts/format_for_training.py (streaming adapters, dedup, reject taxonomy, deterministic hash split, --verify-template, --sample)
[20:40:00] Bug: prefix-based dedup key collapsed kernel 5,000 -> 20; switched to exact full-record hashing (documented in DATA_PIPELINE.md)
[20:45:00] Formatted 11 categories; all passed --verify-template after fixing the verifier to check the untruncated render
[21:00:00] OOM killed the 8192-token probe; system now has 64G zram (swappiness 180)
[21:05:00] agent_tool re-run under systemd-run MemoryMax=12G with 4 workers: 663,056 train / 13,343 val, --verify-template PASS
[21:20:00] Long-context probe (gradient checkpointing on, 12G cap): 41tok=5.1GiB/4.9s, 880tok=9.3GiB/116s, 1804tok=12.4GiB/271s, 4096/6144/8192 = OOM-killed
[21:35:00] Final max_length=1024 (fp32 LM head over 248k vocab is the driver). Tokenize-and-drop run for all 12 corpora
[21:40:00] docs/DATA_PIPELINE.md §7, docs/EXPERT_PLAN.md, config.md updated with measured numbers

[19:40:00] AUDIT: verified one commit (372b863), tree clean, 143 datasets downloaded
[19:41:00] A.5 download integrity: 143/143 OK dirs present and non-empty, 0 missing, 0 empty, 0 untracked dirs; real on-disk size 9.44 GiB (API estimate 14.75 GiB)
[19:42:00] FIX: status `bytes` came from HF `usedStorage` (overstated by ~5.7 GB). Patched downloader to log real on-disk bytes; `_status.json` now has `bytes` (on-disk) + `bytes_api_estimate`
[19:44:00] A.2/A.3: re-applied/verified the three scaffold fixes in downloader.py; 7 tests passed
[19:46:00] A.4: dry-run regression check — 192 datasets parsed; with `--download-root /tmp/empty` it still prints 143 download / 49 skip
[19:47:00] A.7: venv-inference loads Qwen3.5 and generates "The capital of France is Paris." (3.01 tok/s); venv (4.37.2) fails with the qwen3_5 ValueError
[19:48:00] A.8/A.9: all 12 LoFT bugs verified against source; LoFT has no .git (fully vendored)
[19:50:00] B.1: chose Option 2; installed peft 0.21.2 + datasets 5.0.1 + accelerate into venv-inference
[19:51:00] B.1: wrote training/finetune.py + orchestrator/config.py (shared parser); smoke = 1 forward+backward OK (loss 2.5217, 3.9s)
[19:52:00] B.2: fixed 14 LoFT bugs (psutil, sample JSON, gradient_checkpointing, use_safetensors, onnx, llama_cpp_dir, merge exit, CLI exit codes, train_config wiring, real tests, README export, adapter path, dead elif, subprocess raises); LoFT tests 5 passed
[19:53:00] C: /tmp/moe_trash_* already gone; preprocessor configs absent; .pytest_cache ignored; no stray files (only upstream `README.md~` files inside downloaded datasets)
[19:54:00] D: wrote scripts/dataset_inventory.py and datasets/downloaded/_manifest.md; 143 datasets, 10 categories, ~4,386,441 records; 0 integrity issues; 2 datasets with no countable data files
[19:56:00] E: rewrote config.md (downloaded_root, manifest, last_run_status, base_model_type, finetune_entrypoint, llama_cpp_dir); all 18 referenced paths resolve
[19:57:00] G: tests/ now 19 passing (config parser errors, list parsing, path_for, build_plan skip reasons)

## Bugs fixed during this session

- downloader `_status.json` byte count used the HF API `usedStorage`
  (15.84 GB) instead of real on-disk bytes (10.13 GB). Fixed: the
  downloader now records real bytes; `_status.json` keeps both values.
- `scripts/dataset_inventory.py --fix-status` initially overwrote
  `bytes_api_estimate` with the corrected value; fixed to derive it from
  the historical log.

## Blockers

- BLOCKER (resolved): `kernel` folded into the `linux_kernel` expert together
  with `linux` + `generated_lineageos` (25,467 records).
- BLOCKER (resolved): `mql5` has no downloaded data; `generated_mql5`
  (3,032 records) is formatted and kept as the optional `mql5_optional` expert.
- BLOCKER: **`debug_review` (coding_debug) is not trainable at max_length=1024**
  — 98% of records truncate and 97.5% end with an all-zero assistant mask
  (code traces have p50 ~4.9k tokens). Raising max_length is not possible on
  this machine (2048 tokens = 12.4 GiB and thrashing; 4096+ OOM). Plan:
  load the base weights in bf16 and/or use a chunked/fused cross-entropy so
  the 248k-vocab logits are never materialised, then re-run
  `scripts/tokenize_and_drop_check.py --category coding_debug`. The formatted
  corpus is already complete; only the training-side memory limit blocks it.
- BLOCKER (resolved earlier): transformers 4.37.2 cannot load `qwen3_5` —
  resolved by B.1 Option 2 (`training/finetune.py` + `venv-inference`).
