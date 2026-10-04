# MoE Orchestrator

A single consolidated folder for turning one small base model
(Qwen3.5-0.8B) into a Mixture-of-Experts system: curated datasets are
downloaded and grouped by category, one LoRA expert is fine-tuned per
domain with LoFT, and a router dispatches each prompt to the best expert
inside the DeepSeek CLI harness.

Nothing here trains or downloads on its own. Every tunable lives in
[`config.md`](config.md); the resume anchor is
[`MoE_ToDo_List.md`](MoE_ToDo_List.md).

## Layout

```
config.md              single source of truth for all tunables
MoE_ToDo_List.md       resume anchor: checkboxes + progress log
models/                base HF model + GGUF (git-ignored)
datasets/
  generated/           hand-made data (lineageos, mql5) (git-ignored)
  downloaded/          downloader output (git-ignored)
  scripts/             downloader.py
  sources/             ReallyHelpfulClean.md, search_terms.txt
LoFT/                  finetune/merge/export/quantize/chat toolkit
orchestrator/          router (IR3DE), experts, ui
training/scripts/      expert training + conversion scripts
docs/                  ARCHITECTURE.md, LoFT_KNOWN_BUGS.md
scripts/               operational helpers
tests/                 parser/unit tests (no network)
```

## Quickstart

```bash
cd ~/MoE-orchestrator
source venv/bin/activate

# nothing is downloaded — lists every decision, sizes and skips
python datasets/scripts/downloader.py --dry-run

# when ready, for real:
# python datasets/scripts/downloader.py
```

Two Python 3.11 environments live here:

- `venv/` — the pinned LoFT training stack (transformers 4.37.2,
  peft 0.8.2, torch 2.2.2+cpu). Used for fine-tuning and tests.
- `venv-inference/` — transformers 5.18.0 + torch 2.14.1+cpu. Qwen3.5
  (`model_type: qwen3_5`) cannot be loaded by transformers 4.37.2, so HF
  model loading and inference use this environment instead.

```bash
# load the base model on CPU and generate (uses the inference venv)
./venv-inference/bin/python scripts/moe_smoke.py
```

See [`config.md`](config.md) for every tunable and
[`MoE_ToDo_List.md`](MoE_ToDo_List.md) for what is done and what is next.
The architecture plan lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
