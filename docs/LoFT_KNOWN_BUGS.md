# LoFT — known bugs

Every bug below was verified against `LoFT/` source and **fixed in place**
on 2026-10-04 (this session). LoFT is vendored into the parent repo, so the
fixes live in the parent commit. Re-verified by `LoFT/tests/test_cli.py`.

| # | Bug | Status | Fix location |
|---|-----|--------|--------------|
| 1 | `psutil` imported by 5 modules but missing from `requirements.txt` and `setup.py`. | FIXED | `requirements.txt`, `setup.py` |
| 2 | `data/sample_finetune_data.json` was malformed JSON (missing `{`). | FIXED | `data/sample_finetune_data.json` |
| 3 | `--gradient_checkpointing` parsed but never forwarded to `run_finetune`. | FIXED | `loft/cli.py` `_resolve_finetune()` → `loft/train.py` |
| 4 | `--use_safetensors` parsed but ignored (hardcoded `True`). | FIXED | `loft/train.py` `from_pretrained(use_safetensors=use_safetensors)` |
| 5 | `--format onnx` accepted by parser but rejected by `export.py`. | FIXED (option b: removed `onnx` from choices) | `loft/cli.py` |
| 6 | Hardcoded `../llama.cpp` paths with "#please change this" comments in 3 files; README said `make` instead of CMake. | FIXED | `loft/{export,quantize,chat}.py`, `loft/cli.py`, `README.md` |
| 7 | `merge.py` printed a warning and `return`ed on failure. | FIXED | `loft/merge.py` `sys.exit(1)` |
| 8 | No CLI exit codes for errors (scripts could not detect failure). | FIXED | `loft/cli.py` `main()` returns 1, `__main__` guard |
| 9 | `train_config.yaml` was dead — no code read it. | FIXED (wired up via `loft finetune --config`) | `loft/cli.py` `_resolve_finetune()` |
| 10 | `test_adapter.py` was a hardcoded manual script, not a test. | FIXED (real pytest module, skips without weights) | `loft/test_adapter.py`, new `LoFT/tests/` |
| 11 | README `loft export` example passed a positional arg the parser rejects. | FIXED | `LoFT/README.md` (now uses `--model_dir`) |
| 12 | Example adapter shipped no weights and pointed at the author's Mac cache. | FIXED (public model id + explanatory README) | `adapter/adapter_v1/` |
| 13 | `export.py` dead `elif`: `script_path` and `binary_path` were identical. | FIXED | `loft/export.py` (distinct python script + compiled binary paths) |
| 14 | Subprocess failures were caught and swallowed; functions returned 0. | FIXED | `loft/{export,quantize,chat}.py` now `raise SystemExit(...)` |

Note: bugs 3 and 4 affect LoFT's own `finetune` path, which is superseded
for this project by `training/finetune.py` (LoFT pins transformers 4.37.2,
which cannot load `qwen3_5`). LoFT is kept for the llama.cpp
merge/export/quantize/chat utilities, which now work with an explicit
`LFT_LLAMA_CPP_DIR` / `--llama_cpp_dir`.
