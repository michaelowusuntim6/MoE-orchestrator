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
- `venv-inference/` — transformers 5.18.0 + torch 2.14.1+cpu + peft 0.21.2.
  Qwen3.5 (`model_type: qwen3_5`) cannot be loaded by transformers 4.37.2,
  so HF loading, inference and expert training use this environment.

```bash
# load the base model on CPU and generate (uses the inference venv)
./venv-inference/bin/python scripts/moe_smoke.py

# verify the LoRA training path reaches a forward/backward pass (no training)
./venv-inference/bin/python training/finetune.py --smoke

# real training happens only with --train:
# ./venv-inference/bin/python training/finetune.py --train \
#   --dataset datasets/downloaded/python/<owner>__<name>/<file>.jsonl \
#   --expert python
```

## Data

143 datasets (9.44 GiB, ~4.39M records) are downloaded under
`datasets/downloaded/<category>/`. The per-dataset inventory with record
counts and exclusion candidates is `datasets/downloaded/_manifest.md`
(regenerate with `./venv/bin/python scripts/dataset_inventory.py`).

To format downloaded datasets for training:

```bash
./venv-inference/bin/python datasets/scripts/format_for_training.py
```

Outputs land in `datasets/formatted/<category>/{train,val}.jsonl` with a
`manifest.json` per category. The formatter uses the model's native chat
template exactly: it writes `{"messages": [...]}` records and never inserts
`<|im_start|>`/`<|im_end|>` itself — the tokens are added by
`tokenizer.apply_chat_template()` at tokenize time. Verify with
`--verify-template`, and read `docs/DATA_PIPELINE.md` for the schema, dedup
key, reject taxonomy and the measured `max_length` limit.

See [`config.md`](config.md) for every tunable and
[`MoE_ToDo_List.md`](MoE_ToDo_List.md) for what is done and what is next.
The architecture plan lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
