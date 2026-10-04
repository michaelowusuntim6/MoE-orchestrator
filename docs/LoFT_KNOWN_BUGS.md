# LoFT — known bugs (reference only)

The previous working copy (`~/CLI_harnesses/LoFT-custom`) was deleted and
re-cloned fresh in `~/MoE-orchestrator/LoFT`. None of the fixes below are
applied to the fresh clone. This file preserves the audit so a later
session can re-apply the fixes deliberately.

Source: the twelve-bug audit prompt from the previous LoFT session.
"Previous status" is what the deleted working copy had committed when it
was removed.

| # | Bug | Previous status |
|---|-----|-----------------|
| 1 | `psutil` is imported by `train.py`, `merge.py`, `export.py`, `quantize.py`, `chat.py` but is not declared in `requirements.txt` or `setup.py`; a clean install crashes. | **Fixed** — committed as "Fix 1: declare psutil in requirements.txt and setup.py". |
| 2 | `data/sample_finetune_data.json` is malformed JSON (a row is not closed correctly). | **Fixed** — committed as "Fix 2: repair malformed sample_finetune_data.json". |
| 3 | `--gradient_checkpointing` is parsed by the CLI but never forwarded to `run_finetune()`, so the flag is silently ignored. | **Fixed** — committed as "Fix 3: forward --gradient_checkpointing to run_finetune". |
| 4 | `--use_safetensors` is parsed but ignored: `train.py` hardcodes `use_safetensors=True` in `from_pretrained`. | **Fixed** — committed as "Fix 4: honor --use_safetensors in the model loader". |
| 5 | CLI accepts `--format onnx` but `export.py` raises `ValueError` for anything except `gguf`. | **Fixed (option b)** — committed as "Fix 5: remove unsupported onnx format choice from CLI". |
| 6 | `export.py`, `quantize.py`, `chat.py` reference a hardcoded `../llama.cpp` path with "#please change this to original llama.cpp folder" comments; README says `make` but code expects CMake `build/bin/*`. | **Not applied** — still present in the fresh clone. |
| 7 | `merge.py` prints a warning and `return`s when `merge_and_unload` fails, so scripts cannot detect failure. | **Fixed** — committed as "Fix 7: merge exits non-zero on failure". |
| 8 | Every subcommand prints an error and exits 0, so shell scripts cannot detect failures. | **Fixed** — committed as "Fix 8: CLI exits non-zero on subcommand failure". |
| 9 | `train_config.yaml` is dead: no code reads it. Either wire up a `--config` flag or delete it and its README references. | **Not applied**. |
| 10 | `test_adapter.py` is a hardcoded manual script, not a real test. Convert to pytest or replace with a real `tests/` directory. | **Not applied**. |
| 11 | README's `loft export` example passes a positional argument the parser does not accept; it must use `--model_dir`. | **Not applied**. |
| 12 | `adapter/adapter_v1/` ships a config with no weights and a `base_model_name_or_path` pointing at the original author's Mac path. | **Not applied**. |

Re-apply these deliberately in the fresh clone once expert training starts.
