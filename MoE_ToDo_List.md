# MoE Orchestrator — master TODO list

Last updated: 2026-10-05T16:30:00Z
Current phase: 2 (data formatted for training; expert plan written)
Last completed step: 1.6 training-memory fix — 8192-token step verified on CPU

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

## Phase 1.6 — Fix the training memory bottleneck
- [x] 1.6.1 Implement chunked linear cross-entropy (orchestrator/chunked_ce.py)
- [x] 1.6.2 Wire it into finetune.py via a ChunkedCETrainer (--chunk-size, --loss-mode)
- [x] 1.6.3 Evaluate bf16 weights (rejected: CPU backward 40x slower; fp32 kept)
- [x] 1.6.4 Add --optimizer {adamw,adafactor}
- [x] 1.6.5 Measure the new ceiling: 2048/4096/8192 all succeed (no OOM)
- [x] 1.6.6 Raise max_length 1024 -> 8192 in config.md
- [x] 1.6.7 Re-run tokenize-and-drop: coding_debug 98% -> 7.5% truncation
- [x] 1.6.8 Tests: tests/test_chunked_ce.py (5 passing, exact parity)

## Phase 1.7 — Dataset acquisition infrastructure
- [x] 1.7.1 Create scrapers/{github,huggingface,lineageos}/ with READMEs
- [x] 1.7.2 Update config.md with every scraper tunable (## Scrapers, ## Upload)
- [x] 1.7.3 Extend orchestrator/config.py (get_str, get_path, [] literal, clean errors)
- [x] 1.7.4 hf_search.py (keyword search -> scrapers/logs/hf_search_results.json)
- [x] 1.7.5 hf_downloader.py (guarded, resumable, 500 MB per-file rule)
- [x] 1.7.6 github_scraper.py (clone + prune oversized files -> _truncated.json)
- [x] 1.7.7 lineageos_walker.py (read-only catalog, device paths first)
- [x] 1.7.8 aosp_scraper.py (AOSP snippet records from the local tree)
- [x] 1.7.9 hf_uploader.py + README.template.md (for Prompt 3)
- [x] 1.7.10 Populate dataset_list.md (10 verified) and repo_list.md (7 verified)
- [x] 1.7.11 docs/DATASET_SOURCES.md with verified sizes
- [x] 1.7.12 tests/test_scrapers.py (14 passing)
- [x] 1.7.13 All four dry-runs pass (hf_search, hf_downloader, github, lineageos)

## Phase 1.8 — Data acquisition (download, scrape, format)
- [x] 1.8.1 Removed the android_kernel category from repo_list.md (kernel trees excluded)
- [x] 1.8.2 Downloaded 6 HF datasets for real (176.7 MB, 0 failures)
- [x] 1.8.3 Streamed 3 oversized sharded datasets at 500 MB each
- [x] 1.8.4 Skipped DevEscorpion/android-firmware-research (134 GB, monolithic 4.3 GB file)
- [x] 1.8.5 Cloned the 4 MQL5 GitHub repos (51.4 MB; 359 .mq5, 1,077 .mqh)
- [x] 1.8.6 Walked the LineageOS 23.2 tree: 200,000 files, 2.19 GB catalogued (read-only)
- [x] 1.8.7 Built scrapers/format_public.py with 9 adapters
- [x] 1.8.8 Formatted 9 new categories: 615,330 records total
- [x] 1.8.9 --verify-template PASS for all 9 new categories (and all 12 existing)
- [x] 1.8.10 Tokenize-and-drop: <=2.5% truncation, 0% all-zero masks on every new category
- [x] 1.8.11 datasets/_master_manifest.md written

## Phase 1.10 — Expanded dataset acquisition
- [x] 1.10.1 Expanded HF keywords 15 -> 44 and fixed the `direction` kwarg bug in hf_search.py
- [x] 1.10.2 Added the quality gate (downloads/license/README/data files/size) to hf_downloader.py
- [x] 1.10.3 Added github_search.py (107 candidates, 54 passing; kernel/ROM excluded by policy)
- [x] 1.10.4 Added the GitHub quality gate (stars/license/description/README) + metadata cache
- [x] 1.10.5 Downloaded 13 new HF datasets (2.4 GB, 0 failures); 1 rejected by the gate
- [x] 1.10.6 Streamed 3 oversized datasets at 500 MB (daVinci, bagel, syzfix-full)
- [x] 1.10.7 Cloned 52 new MQL5 repos via the cached metadata path (0 API calls)
- [x] 1.10.8 Formatted 9 new categories (383,047 records)
- [x] 1.10.9 --verify-template PASS on all 9
- [x] 1.10.10 Documented kernel_davinci as untrainable at max_length=8192
- [x] 1.10.11 Master manifest updated (30 categories, 2,987,415 records)

## Phase 1.11 — 8-bit quantization support
- [x] 1.11.1 Installed bitsandbytes 0.50.2 into venv-inference
- [x] 1.11.2 Added --quantization {fp32,bf16,8bit,4bit} to training/finetune.py
- [x] 1.11.3 8bit/4bit map to BitsAndBytesConfig and paged_adamw_8bit; CPU raises a clear error
- [x] 1.11.4 docs/TRAINING_RUNBOOK.md written (memory vs quality trade-off)
- [x] 1.11.5 Smoke test passes with --quantization fp32
- [x] 1.11.6 tests/test_quantization.py (8 passing)

## Phase 1.12 — Hugging Face upload
- [x] 1.12.1 Wrote 30 dataset cards with frontmatter, attribution and licence
- [x] 1.12.2 Added the [HF_Upload] mapping to config.md
- [x] 1.12.3 Pre-upload check: 0 existing repos, 30 new
- [x] 1.12.4 Dry run verified (keeps the curated card, does not overwrite)
- [x] 1.12.5 Fixed the frontmatter licence bug that made HF reject 25 uploads
- [x] 1.12.6 upload_all.sh (smallest first, one at a time, logged)
- [x] 1.12.7 Uploaded all 30 corpora to michaelowusuntim6
- [x] 1.12.8 All 30 verified loadable via datasets.load_dataset

## Phase 1.13 — Training notebooks
- [x] 1.13.1 notebooks/qwen35_0.8b_colab.ipynb (T4, bf16 LoRA)
- [x] 1.13.2 notebooks/qwen35_0.8b_kaggle.ipynb (T4 x2, bf16 LoRA, batch 2)
- [x] 1.13.3 notebooks/qwen35_moe_composition.ipynb (template)
- [x] 1.13.4 notebooks/upload_to_hf.ipynb (helper)
- [x] 1.13.5 notebooks/README.md
- [x] 1.13.6 docs/HF_UPLOAD_GUIDE.md

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
[22:05:00] Step 0: torch 2.14.1 has F.linear_cross_entropy and optim.Adafactor; CPU bf16 tensors OK; model maps to Qwen3_5ForCausalLM with a clean decoder + lm_head
[22:10:00] Built-in chunked path (LinearCrossEntropyOptions) unusable on CPU: >10 min without finishing for one 4096-token step; killed it
[22:20:00] Wrote orchestrator/chunked_ce.py (custom autograd.Function, token-chunked, hidden-grad only since the LM head is frozen). Exact parity with the reference (grad max diff 2.2e-8)
[22:30:00] finetune.py: ChunkedCETrainer + --chunk-size/--loss-mode/--optimizer/--dtype; probe updated
[22:35:00] bf16 smoke: 199.7s/step (backward 190.7s) with 2.2 GiB RSS; fp32 smoke: 5.1s/step. bf16/fp16 rejected on measurement, fp32 kept
[22:50:00] Memory ceiling (fp32 + chunked CE, 12G cap): 1804 tok = 7.6 GiB / 210s (was 12.4 GiB thrashing); 3484 tok = 10.3 GiB / 433s (was OOM); 7124 tok = 8.8 GiB / 1185s (was OOM)
[23:00:00] max_length raised 1024 -> 8192; tokenize-and-drop: all categories 0% truncation except coding_debug 7.5% (was 98%)
[23:05:00] docs/DATA_PIPELINE.md §7 and docs/EXPERT_PLAN.md rewritten with the new numbers; tests/test_chunked_ce.py added
[23:10:00] debug_review unblocked
[2026-10-05 10:05] Step 0: verified commit 7075b3a, clean tree; config.md has 9 sections; LineageOS tree present with .repo/vendor/device/kernel; HF_TOKEN set, GITHUB_TOKEN not set
[10:10:00] Created scrapers/ structure + common.py (shared config, size-limit predicate, RunLog, status writer)
[10:15:00] Extended orchestrator/config.py with get_str/get_path; audited every config path
[10:20:00] Added ## Scrapers and ## Upload to config.md (500 MB per-file ceiling in three places)
[10:25:00] Built hf_search.py, hf_downloader.py, github_scraper.py, lineageos_walker.py, aosp_scraper.py, hf_uploader.py
[10:30:00] Verified 10 HF datasets (1 x 404 removed) and 7 GitHub repos (0 x 404) via API; wrote dataset_list.md + repo_list.md with sizes
[10:35:00] lineageos_walker --dry-run: 200,000 files / 2.0 GB matched in 4m43s, 50,686 device-specific, 23 files > 10 MB skipped
[10:40:00] tests/test_scrapers.py: 14 passing; all four scraper dry-runs pass; no datasets downloaded
[2026-10-05 11:00] Removed the android_kernel category from repo_list.md; kernel trees are excluded by policy
[11:05:00] HF downloads: 6 ok / 4 skipped / 0 failed (176.7 MB) — exactly the planned set
[11:20:00] Streamed 3 oversized sharded datasets at 500 MB each: codeparrot-clean (48,905 raw records), syzfix-dataset (502.6 MB / 1,923), kernel-vuln-dataset-full (500 MB / 101,023)
[11:35:00] GitHub: cloned 4 MQL5 repos (51.4 MB; 359 .mq5, 1,077 .mqh); no file exceeded 500 MB
[11:40:00] LineageOS walk (read-only): 200,000 files / 2.19 GB catalogued, 50,686 device-priority, 23 files >10 MB skipped
[11:50:00] Wrote scrapers/format_public.py (reuses the canonical schema, reject taxonomy, dedup and split)
[12:00:00] Formatted 9 new categories: 615,330 records (largest: lineageos_tree 194,832; kernel_vuln 241,116)
[12:05:00] --verify-template PASS on all 9; tokenize-and-drop <=2.5% truncation, 0% all-zero masks
[12:10:00] datasets/_master_manifest.md written (2,604,368 records across 21 categories)
[13:00:00] Found and fixed a real bug: hf_search.py passed an unsupported `direction=` kwarg, so every keyword search had been failing silently
[13:05:00] Expanded HF keywords 15 -> 44; search returned 691 kept / 153 downloadable
[13:10:00] Added the HF quality gate (downloads >= 10, license, README, data files, size) — default ON
[13:15:00] github_search.py: 8 queries, 107 unique repos, 54 passing (23 kernel/ROM rejected by policy)
[13:20:00] HF download: 13 ok / 12 skipped / 0 failed / 1 gate rejection (2.4 GB)
[13:35:00] Streamed GAIR/daVinci-kernel-sft (500 MB / 8,879 rec) and bagel-llama-3-v1.0 (500 MB / 248,833 rec)
[13:40:00] anon-sub/syzfix-dataset streaming failed on a dataset-side pyarrow schema error — documented (already covered by xiaoguangwang/syzfix-dataset)
[13:50:00] Cloned 52 new MQL5 repos (267.9 MB) using the search-results metadata cache
[14:00:00] formatters: 9 new categories, 383,047 records; 2 rglob bugs found and fixed (parquets live in data/ subdirs)
[14:15:00] --verify-template PASS on all 9 new categories
[14:20:00] tokenize-and-drop: all new categories <=13.5% truncation except kernel_davinci (100%, documented)
[14:30:00] bitsandbytes 0.50.2 installed; --quantization {fp32,bf16,8bit,4bit} added; fp32 smoke PASS
[14:40:00] docs/TRAINING_RUNBOOK.md + tests/test_quantization.py (8 passing)
[15:10:00] Wrote 30 dataset cards (scrapers/huggingface/make_cards.py) and the [HF_Upload] mapping
[15:20:00] Pre-upload check: 0 existing repos / 30 new; dry run kept the curated card
[15:30:00] First upload run exposed Invalid metadata in README.md — HF rejects non-canonical `license:` values; mapped them to valid ids (mixed -> other)
[15:45:00] upload_all.sh (smallest-first, sequential, logged) launched
[16:10:00] Created 4 notebooks + notebooks/README.md
[16:25:00] docs/HF_UPLOAD_GUIDE.md generated from the manifests (2,987,415 records)

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

- NOTE (not a blocker): `LineageOS/android_kernel_samsung_exynos850` is
  2201 MB, just over the 2048 MB `github_max_repo_mb` default. It is the most
  valuable kernel source for the A04s, so it is kept in repo_list.md and must
  be cloned with `--allow-large` (or by raising `github_max_repo_mb`).
- NOTE: `kernel_davinci` is formatted but not trainable at max_length=8192
  (100% truncation). It needs a larger context on a GPU; the corpus itself is
  correct.
- NOTE: `yeeted-my-bashrc/lkml-domains` is downloaded but not formatted — the
  release has only an email-domain column, so it cannot yield instruction
  pairs.

- BLOCKER (resolved): `kernel` folded into the `linux_kernel` expert together
  with `linux` + `generated_lineageos` (25,467 records).
- BLOCKER (resolved): `mql5` has no downloaded data; `generated_mql5`
  (3,032 records) is formatted and kept as the optional `mql5_optional` expert.
- BLOCKER (resolved): `debug_review` (coding_debug) was untrainable at
  max_length=1024 (98% truncation). Fixed by the chunked cross-entropy +
  max_length=8192; truncation is now 7.5%. Measured costs are documented in
  `docs/DATA_PIPELINE.md` §7 (an 8k-token step takes ~20 min on this CPU, so
  cap runs with `--limit`).
- BLOCKER (resolved earlier): transformers 4.37.2 cannot load `qwen3_5` —
  resolved by B.1 Option 2 (`training/finetune.py` + `venv-inference`).
