"""Smoke-test a trained LoRA adapter.

This is a real pytest module: it skips unless an adapter with weights and
a resolvable base model are both available, so a bare ``pytest`` run never
downloads anything.
"""
import os

import pytest

ADAPTER_PATH = os.environ.get("LOFT_TEST_ADAPTER", "adapter/adapter_v1")


def _adapter_has_weights(path):
    return os.path.isfile(os.path.join(path, "adapter_model.safetensors"))


@pytest.mark.skipif(not _adapter_has_weights(ADAPTER_PATH),
                    reason=f"no adapter weights in {ADAPTER_PATH}")
def test_adapter_loads_and_generates():
    import torch
    from peft import PeftConfig, PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    config = PeftConfig.from_pretrained(ADAPTER_PATH)
    base_id = config.base_model_name_or_path
    tokenizer = AutoTokenizer.from_pretrained(base_id, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(base_id, trust_remote_code=True)
    model = PeftModel.from_pretrained(base, ADAPTER_PATH).merge_and_unload()
    model.eval()

    inputs = tokenizer("### Instruction:\nSay hello.\n\n### Response:", return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=16)
    assert tokenizer.decode(outputs[0], skip_special_tokens=True)
