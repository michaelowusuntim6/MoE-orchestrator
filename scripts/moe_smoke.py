"""CPU smoke test: load the base HF model and generate a few tokens.

Qwen3.5 is `model_type: qwen3_5`, which needs transformers 5.x, so run
this with the inference venv:

    cd ~/MoE-orchestrator
    ./venv-inference/bin/python scripts/moe_smoke.py

Slow is expected on CPU; the goal is only to prove the weights load and
one forward/generate pass works.
"""
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

d = "models/Qwen3.5-0.8B"
tok = AutoTokenizer.from_pretrained(d, trust_remote_code=True)
m = AutoModelForCausalLM.from_pretrained(
    d,
    torch_dtype=torch.float32,
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)
m.eval()
inputs = tok("The capital of France is", return_tensors="pt")
t = time.time()
with torch.no_grad():
    out = m.generate(**inputs, max_new_tokens=10, do_sample=False)
print("Out:", tok.decode(out[0], skip_special_tokens=True))
print(f"tokens/sec: {10 / (time.time() - t):.1f}")
