# MoE Orchestrator — Configuration

Every value in this file is a tunable. Scripts read it; you edit
it. Changes take effect on the next run.

## Project

name: MoE-orchestrator
root: /home/mike/MoE-orchestrator

## Models

# Base HF model used for fine-tuning experts.
base_hf_path: models/Qwen3.5-0.8B
base_hf_dtype: float32
base_hf_device: cpu

# Qwen3.5 (model_type qwen3_5) needs transformers 5.x, which the
# LoFT-pinned venv (transformers 4.37.2) does not provide. HF loading
# and the smoke test use this second venv instead.
hf_inference_venv: venv-inference

# GGUF model used by llama.cpp for inference.
base_gguf_path: models/Qwen3.5-0.8B-Q4_K_M.gguf
base_gguf_quant: Q4_K_M

# llama.cpp server binary and default port.
llama_server_bin: /home/mike/llama.cpp/build/bin/llama-server
llama_server_port: 8080
llama_server_context: 8192
llama_server_threads: 2

## Datasets

# Where new downloads land.
download_root: datasets/downloaded

# Already-present generated data.
generated_lineageos: datasets/generated/11_lineageos.jsonl
generated_mql5: datasets/generated/14_mql5.jsonl

# Source list of datasets to evaluate/download.
source_list: datasets/sources/ReallyHelpfulClean.md
category_list: datasets/sources/search_terms.txt

# Where the downloader writes its status file.
status_file: datasets/downloaded/_status.json
log_file: datasets/downloaded/_download.log

## Downloader

# HuggingFace token: read from env var HF_TOKEN, never store in
# this file.
hf_token_env: HF_TOKEN

# Concurrency.
workers: 4
retry_attempts: 4
retry_backoff_seconds: 3

# Size filter (bytes). Skip datasets outside this range.
max_size_bytes: 524288000
min_size_bytes: 102400

# Skip lists.
skip_gated: true
skip_ids:
  - bigcode/the-stack-python
  - codeparrot/codeparrot-clean

# Categories to download. Leave empty for all.
categories: []

# Per-download wall-clock timeout (seconds).
timeout_seconds: 900

## Training

# LoRA hyperparameters for the experts.
lora_r: 8
lora_alpha: 16
lora_dropout: 0.1
num_train_epochs: 1
batch_size: 1
grad_accumulation: 4
learning_rate: 0.0002
max_length: 128
gradient_checkpointing: true
save_strategy: epoch
save_total_limit: 1
output_dir: training/adapters

## Router (IR3DE)

# Placeholder for the IR3DE router configuration.
# Populate after the router is implemented.
router_type: manual
ir3de_enabled: false
ir3de_lambda: 0.01

## Experts

# Name and dataset root for each expert. Populate as experts
# are trained.
expert_count: 0

## UI

# Which agent harness wraps the orchestrator.
agent_harness: /home/mike/CLI_harnesses/gemini-cli_custom
expert_header_format: "expert · {name} · {params}B · prompt {n}/{max}"
