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

## Scrapers — acquiring more datasets

`scrapers/` holds the acquisition infrastructure for the next campaign
(Android/LineageOS, Exynos850 kernel, MQL5, security, coding). Everything
reads the same `config.md`, and no single downloaded file may exceed 500 MB.

```bash
cd ~/MoE-orchestrator

# 1. see what each tool would do — none of these download anything
./venv-inference/bin/python scrapers/huggingface/hf_search.py --dry-run
./venv-inference/bin/python scrapers/huggingface/hf_downloader.py --dry-run
./venv-inference/bin/python scrapers/github/github_scraper.py --dry-run
./venv-inference/bin/python scrapers/lineageos/lineageos_walker.py --dry-run

# 2. when ready, drop --dry-run (reads HF_TOKEN / GITHUB_TOKEN from the env)
# ./venv-inference/bin/python scrapers/huggingface/hf_downloader.py

# 3. catalog the local LineageOS tree (read-only) and extract AOSP snippets
./venv-inference/bin/python scrapers/lineageos/lineageos_walker.py --sample 500
./venv-inference/bin/python scrapers/lineageos/aosp_scraper.py --dry-run
```

Outputs: `datasets/public/{huggingface,github,lineageos_tree}/`, with logs in
`scrapers/logs/`. Verified sources and sizes are in
[`docs/DATASET_SOURCES.md`](docs/DATASET_SOURCES.md); see
[`scrapers/README.md`](scrapers/README.md) for per-tool flags.

### Acquisition status (2026-10-05)

The first campaign ran: 6 HF datasets downloaded, 3 oversized sharded
datasets streamed at 500 MB each, 4 MQL5 repos cloned (kernel repos
deliberately excluded — the local tree covers kernel source), and the
LineageOS tree walked read-only (200,000 files, 2.19 GB). Nine new formatted
corpora were produced — **615,330 records** — all template-verified and
≤2.5% truncated at `max_length = 8192`:

```bash
./venv-inference/bin/python scrapers/format_public.py --all
./venv-inference/bin/python datasets/scripts/format_for_training.py --verify-template \
    --category supportbench_lineageos --category lineageos_tree --category kernel_vuln
```

The full inventory (21 categories, 2,604,368 records) is
[`datasets/_master_manifest.md`](datasets/_master_manifest.md).

### Expansion + 8-bit training (later 2026-10-05)

```bash
# search and gate new sources before downloading anything
./venv-inference/bin/python scrapers/huggingface/hf_search.py --all
./venv-inference/bin/python scrapers/github/github_search.py --append

# download only what passes the gate (default: on)
./venv-inference/bin/python scrapers/huggingface/hf_downloader.py --all --quality-gate
./venv-inference/bin/python scrapers/github/github_scraper.py --all --quality-gate

# format the new public sources (9 more categories)
./venv-inference/bin/python scrapers/format_public.py --all

# train: fp32 here, 8-bit on Colab/Kaggle
./venv-inference/bin/python training/finetune.py --smoke --quantization fp32
./venv-inference/bin/python training/finetune.py --train --quantization 8bit \
    --dataset datasets/formatted/code_review/train.jsonl --expert debug_review
```

The project now holds **30 categories / 2,987,415 records**. Precision,
memory and where-to-run guidance is in
[`docs/TRAINING_RUNBOOK.md`](docs/TRAINING_RUNBOOK.md).

## Datasets on Hugging Face

All 30 formatted corpora are published at
<https://huggingface.co/michaelowusuntim6>.

See [`docs/HF_UPLOAD_GUIDE.md`](docs/HF_UPLOAD_GUIDE.md) for the full list with
links, record counts, sources and licences.

Train on Colab: [`notebooks/qwen35_0.8b_colab.ipynb`](notebooks/qwen35_0.8b_colab.ipynb)
(Kaggle P100 variant: [`notebooks/qwen35_0.8b_kaggle.ipynb`](notebooks/qwen35_0.8b_kaggle.ipynb)).
