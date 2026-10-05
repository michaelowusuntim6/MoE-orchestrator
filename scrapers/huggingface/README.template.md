---
license: {license}
task_categories:
- text-generation
language:
- en
tags:
- moe-orchestrator
- qwen3.5
- {category}
---

# {name}

## Description

{description}

Formatted for Qwen3.5 LoRA fine-tuning as part of the MoE-orchestrator
project. Records are canonical chat samples:

```json
{"messages": [{"role": "user", "content": "..."},
              {"role": "assistant", "content": "..."}]}
```

No `<|im_start|>` / `<|im_end|>` tokens appear in the content: the model's
own chat template adds them at tokenize time.

## Source attribution

{source}

## License

{license}

## Format

- Qwen3.5 `messages` records (JSONL, one conversation per line)
- Splits: `train.jsonl`, `val.jsonl`
- Records: {records}
- Built with formatter version `{formatter_version}`

## Usage

```python
from datasets import load_dataset
from transformers import AutoTokenizer

ds = load_dataset("{repo_id}", split="train")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-0.8B", trust_remote_code=True)
text = tok.apply_chat_template(ds[0]["messages"], tokenize=False)
print(text)
```

Generated: {generated_at}
