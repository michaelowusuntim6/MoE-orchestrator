# MoE Orchestrator — master TODO list

Last updated: 2026-10-04T16:24:20Z
Current phase: 0 (scaffold)
Last completed step: project folder created

## Phase 0 — Scaffold
- [x] 0.1 Create ~/MoE-orchestrator/ and subfolders
- [x] 0.2 Copy base HF model into models/
- [x] 0.3 Copy base GGUF into models/
- [x] 0.4 Copy generated datasets into datasets/generated/
- [x] 0.5 Clone LoFT fresh from upstream
- [x] 0.6 Create Python 3.11 venv and install dependencies
- [x] 0.7 Write config.md
- [x] 0.8 Write datasets/scripts/downloader.py
- [x] 0.9 Run downloader.py --dry-run
- [x] 0.10 Write README.md
- [x] 0.11 git init and initial commit

## Phase 1 — Dataset download
- [ ] 1.1 Decide which categories to download
- [ ] 1.2 Run downloader.py for real
- [ ] 1.3 Verify each category has at least 3 datasets
- [ ] 1.4 Build a manifest of downloaded datasets

## Phase 2 — Expert selection
- [ ] 2.1 Group downloaded datasets by expert category
- [ ] 2.2 Decide how many experts to train
- [ ] 2.3 Write the expert plan

## Phase 3 — Fine-tune experts
- [ ] 3.1 Fine-tune the first expert with LoFT
- [ ] 3.2 Verify the LoRA adapter
- [ ] 3.3 Convert to GGUF
- [ ] 3.4 Serve with llama.cpp and test inference

## Phase 4 — Router (IR3DE)
- [ ] 4.1 Read the IR3DE paper
- [ ] 4.2 Implement the router
- [ ] 4.3 Test routing against the expert set

## Phase 5 — CLI integration
- [ ] 5.1 Add a provider to the DeepSeek CLI harness that
      routes to the selected expert
- [ ] 5.2 Add the manual expert picker
- [ ] 5.3 Add the expert name to the response header

## Phase 6 — MoE composition
- [ ] 6.1 Decide composition strategy (MergeKit vs router +
      multiple servers)
- [ ] 6.2 Implement composition
- [ ] 6.3 Benchmark the MoE

## Progress log

[16:16:22] 0.1 created ~/MoE-orchestrator/ and all subfolders (models, datasets/{generated,downloaded,scripts,sources}, orchestrator/{router,experts,ui}, training/scripts, docs, scripts)
[16:16:23] 0.3 copied GGUF to models/Qwen3.5-0.8B-Q4_K_M.gguf (549.7 MB)
[16:16:23] 0.4 copied 11_lineageos.jsonl + 14_mql5.jsonl into datasets/generated/, and ReallyHelpfulClean.md + search_terms.txt into datasets/sources/
[16:16:23] 0.5 cloned LoFT fresh from github.com/diptanshu1991/LoFT (HEAD 32fa65a "Update README.md")
[16:16:41] 0.2 copied HF model to models/Qwen3.5-0.8B (1.7G) and removed the two preprocessor configs
[16:17:30] 0.6 created venv (CPython 3.11.15); installed torch 2.2.2+cpu, transformers 4.37.2, peft 0.8.2, datasets 2.19.0, accelerate 0.25.0, sentencepiece 0.1.99, safetensors, psutil, pyyaml, requests, tqdm, pytest — all imports OK
[16:18:30] 0.7 wrote config.md (all tunables, real paths only)
[16:19:00] 0.8 wrote datasets/scripts/downloader.py (env parser, HF API size/gated, resumable, retry+backoff, hard-timeout subprocess, status JSON)
[16:19:28] 0.9 dry run OK: 192 datasets / 10 categories; 143 would download, 49 skipped (44 too_large, 5 too_small); no data downloaded
[16:20:00] fixed two downloader bugs found during dry run (see "Bugs fixed during Phase 0")
[16:21:00] 0.10 wrote README.md, .gitignore, docs/ARCHITECTURE.md, docs/LoFT_KNOWN_BUGS.md, tests/test_downloader.py
[16:24:00] pytest: 7 passed (offline parser tests, tests/test_downloader.py)
[16:25:00] smoke 1: `import torch, transformers, peft, datasets, yaml` -> OK (venv)
[16:26:00] smoke 2 BLOCKED on pinned env: transformers 4.37.2 cannot load `qwen3_5` (ValueError: model type `qwen3_5` not recognized). Model README confirms "latest transformers is required for Qwen3.5".
[16:28:00] smoke 2 FIX: created venv-inference (torch 2.14.1+cpu, transformers 5.18.0); model loads and generates "The capital of France is Paris." at 2.5-3.2 tok/s on CPU (script: scripts/moe_smoke.py)
[16:29:00] smoke 3: downloader --dry-run OK (192 datasets, 143 download / 49 skip)
[16:30:00] smoke 4: LoFT imports OK in pinned venv (`import loft`)
[16:31:00] 0.11 git init + initial commit

## Bugs fixed during Phase 0

- downloader.py `Config.path_for` called `.expanduser()` on a `str`
  (AttributeError). Fixed by constructing a `Path` first.
- downloader.py parsed `categories: []` as the literal string `"[]"`,
  which then filtered out every dataset in `--dry-run`. Fixed the
  markdown parser to treat `[]` as an empty list.

## Notes / decisions

- The old LoFT working copy (`~/CLI_harnesses/LoFT-custom`; the other
  path, `~/CLI_harnesses/LoFT`, did not exist) was moved to
  `/tmp/moe_trash_*` instead of deleted, because `rm -rf` is blocked in
  this environment. It can be deleted manually once the new scaffold is
  trusted.
- LoFT is a fresh upstream clone; none of the previous fixes are applied.
  The full 12-bug audit is preserved in `docs/LoFT_KNOWN_BUGS.md`.

## BLOCKER — transformers pin vs Qwen3.5

The handoff pinned `transformers==4.37.2` for LoFT, but the base model is
`Qwen3_5ForConditionalGeneration` (`model_type: qwen3_5`), which only
exists in transformers 5.x. Exact error under the pinned venv:

    ValueError: The checkpoint you are trying to load has model type
    `qwen3_5` but Transformers does not recognize this architecture.

Workaround applied (no training done, nothing pinned was changed):

- `venv/` stays exactly as specified (transformers 4.37.2) and passes the
  import check; it is used for LoFT and the tests.
- `venv-inference/` (transformers 5.18.0, torch 2.14.1+cpu) loads Qwen3.5
  and runs the CPU smoke test.

Plan for next: when Phase 3 starts, either upgrade `venv`'s transformers
to a 5.x release that still works with the rest of the LoFT stack, or
point LoFT's model loader at the inference venv. Decide before the first
fine-tune; do not train against transformers 4.37.2.
