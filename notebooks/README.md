# Notebooks

Four notebooks covering training, composition and upload for the
MoE-orchestrator corpora.

| notebook | what it does | hardware |
|---|---|---|
| `qwen35_0.8b_colab.ipynb` | Fine-tune Qwen3.5-0.8B with LoRA on one or more published datasets | Colab T4 x1 (16 GB), bf16 LoRA, ~3 GB VRAM |
| `qwen35_0.8b_kaggle.ipynb` | Same, with `device_map="auto"` across both T4s and batch size 2 | Kaggle T4 x2 (32 GB), bf16 LoRA, ~10 min/epoch on 10k records |
| `qwen35_moe_composition.ipynb` | Compose trained expert adapters (PEFT weighted merge or MergeKit) and show the routing decision | template, needs trained experts |
| `upload_to_hf.ipynb` | Validate a local JSONL, attach a card, push it and verify it loads | helper for future sessions |

## Open in Colab

https://colab.research.google.com/github/michaelowusuntim6/MoE-orchestrator/blob/main/notebooks/qwen35_0.8b_colab.ipynb

## Training on multiple datasets

Set `DATASETS` in the config cell:

- Single dataset: `DATASETS = "code-review-qwen35"`
- Concatenate (sequential): `DATASETS = ["code-review-qwen35", "debug-qwen35"]`
- Weighted interleave (recommended): `DATASETS = {"code-review-qwen35": 0.6, "debug-qwen35": 0.4}`
  (weights must sum to 1.0)

## Pushing the trained adapter

Set `PUSH_TO_HUB = True` and set `EXPERT_NAME` to a repo name
(e.g. `code-review-lora`). The adapter uploads to
`michaelowusuntim6/<EXPERT_NAME>` — visible at
https://huggingface.co/michaelowusuntim6.

Adapter naming convention: `<expert-name>-lora` (lowercase, hyphens, always
ends with `-lora`). Never use `-qwen35` on the adapter — the base model is
implicit in the adapter config.

## Datasets

All 30 corpora are published under
https://huggingface.co/michaelowusuntim6. Change `DATASETS` in the config cell
to any of:

```
android-qwen35                lineageos-tree-qwen35       lineageos-support-qwen35
android-malware-qwen35        lineageos-generated-qwen35  kernel-qwen35
linux-qwen35                  kernel-vuln-qwen35          kernel-syzfix-qwen35
kernel-vuln-full-qwen35       linux-kernel-commits-qwen35 linux-kernel-asm-qwen35
linux-kernel-ioctl-qwen35     kernel-davinci-qwen35       mql5-repos-qwen35
mql5-expanded-qwen35          mql5-compile-benchmark      forex-calendar-qwen35
mql5-generated-qwen35         python-qwen35               cpp-qwen35
code-review-qwen35            debug-qwen35                python-codeparrot-qwen35
security-qwen35               security-qa-qwen35          security-expanded-qwen35
agent-tool-qwen35             reasoning-qwen35            uncategorized-qwen35
```

## Notes

- The training notebooks never insert `<|im_start|>`/`<|im_end|>` themselves —
  `tokenizer.apply_chat_template()` does.
- `kernel-davinci-qwen35` needs a GPU with context > 8192.
- `mql5-compile-benchmark` is an **evaluation** set, not training data.
- `SFTTrainer` must receive `max_seq_length=MAX_SEQ_LEN`. Without it, TRL's
  default truncates records silently.
- Reference notebooks: https://github.com/unslothai/notebooks
