# Example adapter (shape reference only)

This directory shows the files LoFT writes after a fine-tune. The adapter
**weights are intentionally absent**:

- `adapter_model.safetensors` is git-ignored upstream and is not shipped here.
- `base_model_name_or_path` points at the public
  `TinyLlama/TinyLlama-1.1B-Chat-v1.0` id rather than the original author's
  local cache path, so the config is portable.

Use it to see the expected layout; train your own adapter to get weights.
