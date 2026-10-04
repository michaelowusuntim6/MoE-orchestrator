import os
import sys
import time
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel, PeftConfig
import psutil

def run_merge(base_model, adapter_dir, output_dir):
    print(f"🔗 Merging LoRA adapter from {adapter_dir} into base model {base_model}...")

    os.makedirs(output_dir, exist_ok=True)

    # Benchmark start
    process = psutil.Process(os.getpid())
    start_ram = process.memory_info().rss / 1024 ** 2
    start_time = time.time()

    # Load base model
    config = PeftConfig.from_pretrained(adapter_dir)
    base_model_id = base_model
    base_model = AutoModelForCausalLM.from_pretrained(base_model, trust_remote_code=True)

    # Wrap with PEFT
    model = PeftModel.from_pretrained(base_model, adapter_dir)

    # Try merging
    try:
        merged = model.merge_and_unload()
        print("✅ LoRA merged successfully.")
    except Exception as e:
        print("⚠️ Error during merge_and_unload. Likely due to model nesting.")
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # Save model and tokenizer
    merged.save_pretrained(output_dir)
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    tokenizer.save_pretrained(output_dir)

    # Benchmark end
    end_time = time.time()
    end_ram = process.memory_info().rss / 1024 ** 2

    # Model size
    model_path = os.path.join(output_dir, "model.safetensors")
    model_size = os.path.getsize(model_path) / 1024 ** 2 if os.path.exists(model_path) else 0

    # Benchmark results
    print("\n📊 Merge Benchmark Results")
    print(f"Peak RAM Used: {max(start_ram, end_ram):.2f} MB")
    print(f"Merge Time: {end_time - start_time:.2f} sec")
    print(f"Merged Model Size: {model_size:.2f} MB")
    print(f"✅ Merged model saved to: {output_dir}")

