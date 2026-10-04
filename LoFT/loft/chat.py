"""Run a GGUF model with llama.cpp's llama-cli."""
import os
import subprocess
import time

import psutil


def run_chat(model_path, prompt, n_tokens=128, llama_cpp_dir=None):
    llama_cpp_dir = os.path.expanduser(
        llama_cpp_dir or os.environ.get("LFT_LLAMA_CPP_DIR") or "../llama.cpp"
    )
    llama_cli = os.path.join(llama_cpp_dir, "build", "bin", "llama-cli")

    if not os.path.isfile(llama_cli):
        raise SystemExit(
            f"error: llama-cli binary not found at: {llama_cli}. "
            "Build llama.cpp (cmake -B build && cmake --build build) or set "
            "--llama_cpp_dir / LFT_LLAMA_CPP_DIR."
        )
    if not os.path.isfile(model_path):
        raise SystemExit(f"error: model file not found: {model_path}")

    print(f"🧠 Running inference on: {model_path}")
    print(f"📨 Prompt: {prompt}")

    command = [llama_cli, "-m", model_path, "-p", prompt, "-n", str(n_tokens)]
    process = psutil.Process(os.getpid())
    start_ram = process.memory_info().rss / 1024 ** 2
    start_time = time.time()

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"error: inference failed: {exc}")

    end_time = time.time()
    end_ram = process.memory_info().rss / 1024 ** 2

    print("\n📊 Inference Benchmark")
    print(f"Inference Time: {end_time - start_time:.2f} sec")
    print(f"Peak RAM Used: {max(start_ram, end_ram):.2f} MB")
    print("✅ Prompt processed and response generated.")
