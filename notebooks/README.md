# Notebooks

Four notebooks covering training, composition and upload for the
MoE-orchestrator corpora.

| notebook | what it does | hardware |
|---|---|---|
| [`qwen35_0.8b_colab.ipynb`](qwen35_0.8b_colab.ipynb) | Fine-tune Qwen3.5-0.8B with LoRA on any of the 30 published datasets | Colab T4 (16 GB), bf16, ~3 GB VRAM |
| [`qwen35_0.8b_kaggle.ipynb`](qwen35_0.8b_kaggle.ipynb) | Same, with `device_map="auto"` across both GPUs and batch size 2 | Kaggle T4 x2 (32 GB), bf16 LoRA, ~10 min/epoch on 10k records |
| [`qwen35_moe_composition.ipynb`](qwen35_moe_composition.ipynb) | Compose trained expert adapters (PEFT weighted merge or MergeKit) and show the routing decision | template, needs trained experts |
| [`upload_to_hf.ipynb`](upload_to_hf.ipynb) | Validate a local JSONL, attach a card, push it and verify it loads | helper for future sessions |

## Open in Colab

```
https://colab.research.google.com/github/michaelowusuntim6/MoE-orchestrator/blob/main/notebooks/qwen35_0.8b_colab.ipynb
```

The GitHub URL resolves once the repository is pushed; until then the notebook
is Colab-compatible and can be opened manually via *File → Upload notebook*.

## Datasets

All 30 corpora are published under
[`michaelowusuntim6`](https://huggingface.co/michaelowusuntim6). Change
`DATASET_NAME` in the first code cell of either training notebook to any of:

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

Full links, record counts, sources and licences are in
[`docs/HF_UPLOAD_GUIDE.md`](../docs/HF_UPLOAD_GUIDE.md).

## Notes

* The training notebooks never insert `<|im_start|>`/`<|im_end|>` themselves —
  `tokenizer.apply_chat_template()` does.
* `kernel-davinci-qwen35` needs a GPU with context > 8192; do not try it on
  the CPU pipeline.
* `mql5-compile-benchmark` is an **evaluation** set, not training data.
* Reference notebooks: <https://github.com/unslothai/notebooks>.
