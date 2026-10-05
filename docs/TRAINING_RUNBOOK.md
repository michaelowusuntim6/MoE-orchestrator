# Training runbook — precision, memory and where to run

`training/finetune.py` is the only training entrypoint. It reads every
hyperparameter from `config.md`, applies the model's own chat template
(`orchestrator/chat_template.py`) and computes the loss with the chunked
cross-entropy (`orchestrator/chunked_ce.py`), so the 248,320-token LM head is
never materialised in full.

## Choosing a precision

```bash
./venv-inference/bin/python training/finetune.py --smoke --quantization fp32
./venv-inference/bin/python training/finetune.py --train \
    --dataset datasets/formatted/code_python/train.jsonl --expert code_python \
    --quantization 8bit
```

| `--quantization` | weights | runtime | quality | where it works |
|---|---:|---|---|---|
| `fp32` (default) | 3.2 GB | full | baseline | **this laptop** — the only supported path here |
| `bf16` | 1.6 GB | full | near-lossless | GPU; numerically fine on this CPU but measured **~40× slower** in backward (41-token smoke: 5.1 s fp32 vs 199.7 s bf16) |
| `8bit` | 0.8 GB | bitsandbytes int8 | near-perfect (99%+) | CUDA only (Colab / Kaggle) |
| `4bit` | 0.4 GB | bitsandbytes nf4 (QLoRA) | good (95–98%) | CUDA only |

`8bit`/`4bit` require bitsandbytes and a CUDA device. bitsandbytes 0.50.2 is
installed in `venv-inference`, but this machine has no CUDA, so the script
exits with a clear error rather than silently falling back:

```
error: --quantization 8bit needs bitsandbytes on a CUDA GPU; this machine has
no CUDA. Use fp32 here, or 8bit on Colab/Kaggle (see docs/TRAINING_RUNBOOK.md).
```

## Optimizer

`--optimizer {adamw,adafactor}`, defaulting to `Training.optimizer` in
config.md (`adafactor`). With `--quantization 8bit|4bit` and `adamw`, the
trainer switches to `paged_adamw_8bit` so the optimizer states are 8-bit too.

Adafactor keeps only rank-1 second-moment factors, which matters much more
for full fine-tuning than for LoRA (only 319,488 adapter parameters are
trained — 0.042% of the model).

## Memory ceiling on this laptop

Measured with `scripts/long_context_probe.py` (fp32 + chunked CE + gradient
checkpointing, inside a 12 GiB systemd cap):

| sequence length | peak RSS | s/step |
|---:|---:|---:|
| 41 | 5.0 GiB | 5.1 |
| 1804 | 7.6 GiB | 210 |
| 3484 | 10.3 GiB | 433 |
| 7124 | 8.8 GiB | 1185 |

`max_length` is 8192 in config.md. It is a cap, not a fixed cost: the Trainer
pads to the longest sequence in a batch.

## Running on Colab / Kaggle

```bash
uv pip install torch transformers peft datasets accelerate bitsandbytes
python training/finetune.py --train \
    --dataset datasets/formatted/<category>/train.jsonl \
    --expert <name> --quantization 8bit --optimizer adamw
```

8-bit weights put the 0.8B model at ~0.8 GB plus 8-bit optimizer states, which
fits comfortably in a free-tier GPU. Quality loss versus fp32 is negligible at
8-bit; 4-bit is the fallback when memory is tighter.

## Safety rules

* Long-running or memory-heavy commands are wrapped:
  `systemd-run --user --scope -p MemoryMax=12G -- <cmd>`.
* `--smoke` performs exactly one forward+backward and never saves; use it to
  validate a configuration before a real epoch.
* The chat template is the law: never hand-insert `<|im_start|>`/`<|im_end|>`.
