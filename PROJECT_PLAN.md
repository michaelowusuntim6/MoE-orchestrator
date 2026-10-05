# MoE Orchestrator — Project Plan

Last updated: 2026-10-05
Current phase: 2 (train experts on 4B)
Next action: smoke test on Colab, then the first Kaggle run

## Phase 0 — Infrastructure
- [x] 30 datasets formatted and on Hugging Face
- [x] Dataset validator (scripts/verify_hf_datasets.py) — 30/30 clean
- [x] Exhaust-all mixer (orchestrator/dataset_mixer.py)
- [x] Training notebooks (Colab smoke, Kaggle real)

## Phase 1 — Model decision
- [x] Research 4B vs 9B — 4B chosen
- [x] Confirm T4 constraint — fp16 (bf16 unsupported on Turing)
- [x] Confirm max context — 32768 safe (NaN bug only >65536)
- [x] Update notebooks for 4B fp16 32K
- [ ] Smoke test on Colab T4 x1 (MAX_SEQ_LEN=2048, LIMIT=100)
- [ ] Confirm loss patch assertion passes

## Phase 2 — Train experts on Kaggle
- [ ] Add marianbusoi/pi-toolcall-dataset to every expert's DATASETS
- [ ] Train pilot expert (code_review) on Kaggle, LIMIT=10000
- [ ] Verify adapter loads via PEFT
- [ ] Run eval against base model (50 domain prompts)
- [ ] If pilot passes: train remaining 7 experts
- [ ] Push all adapters to HF as <expert>-lora

## Phase 3 — Evaluation
- [ ] Build eval harness (scripts/eval_expert.py)
- [ ] Domain questions per expert (out-of-sample)
- [ ] Score base vs expert per question
- [ ] Publish results to docs/EVAL_RESULTS.md

## Phase 4 — Router (IR3DE)
- [ ] Read IR3DE paper
- [ ] Implement router in orchestrator/router/
- [ ] Test routing against the 8 trained experts

## Phase 5 — Pi CLI integration
- [ ] Add provider to Pi CLI that routes to the selected expert
- [ ] Load/unload expert on demand
- [ ] Freeze expert during prompt processing
- [ ] Add manual picker with IR3DE as highlighter

## Phase 6 — MoE composition
- [ ] Decide: router + N adapters vs merged model
- [ ] Implement composition
- [ ] Benchmark the MoE

## Expert → Dataset Mapping

| expert | DATASETS list | target records |
|---|---|---|
| android_rom | ["android-qwen35", "lineageos-tree-qwen35", "lineageos-support-qwen35", "lineageos-generated-qwen35"] | ~383k |
| linux_kernel | ["kernel-qwen35", "linux-qwen35", "kernel-vuln-qwen35", "kernel-vuln-full-qwen35", "kernel-syzfix-qwen35", "linux-kernel-commits-qwen35", "linux-kernel-asm-qwen35", "linux-kernel-ioctl-qwen35"] | ~404k |
| mql5_forex | ["mql5-repos-qwen35", "mql5-expanded-qwen35", "mql5-generated-qwen35", "forex-calendar-qwen35"] | ~86k |
| python_code | ["python-qwen35", "python-codeparrot-qwen35"] | ~195k |
| cpp_code | ["cpp-qwen35"] | ~33k |
| security | ["security-qwen35", "security-qa-qwen35", "security-expanded-qwen35", "android-malware-qwen35"] | ~204k |
| debug_review | ["debug-qwen35", "code-review-qwen35"] | ~637k |
| agent_tool | ["agent-tool-qwen35"] | ~663k |

## Notes

- Every expert's DATASETS list will also include
  `marianbusoi/pi-toolcall-dataset` once it is validated. This is the shared
  tool-calling dataset the user requested.
- fp16 on T4. 32K context. Batch 1, grad accum 8.
- If any dataset shows content as a list instead of a string, stop and fix the
  formatter before training.
- Training runs on Kaggle T4 x2 (32 GB). The Colab notebook is a smoke test
  only — 16 GB cannot hold 4B at 32K.
