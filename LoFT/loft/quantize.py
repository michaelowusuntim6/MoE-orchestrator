"""Quantize a GGUF model with llama.cpp's llama-quantize."""
import os
import subprocess
import time

import psutil


def run_quantize(model_path, output_path, quant_type="Q4_0", llama_cpp_dir=None):
    if not os.path.isfile(model_path):
        raise SystemExit(f"error: input model not found: {model_path}")

    llama_cpp_dir = os.path.expanduser(
        llama_cpp_dir or os.environ.get("LFT_LLAMA_CPP_DIR") or "../llama.cpp"
    )
    quantize_bin = os.path.join(llama_cpp_dir, "build", "bin", "llama-quantize")

    if not os.path.isfile(quantize_bin):
        raise SystemExit(
            f"error: llama-quantize binary not found at: {quantize_bin}. "
            "Build llama.cpp (cmake -B build && cmake --build build) or set "
            "--llama_cpp_dir / LFT_LLAMA_CPP_DIR."
        )

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    command = [quantize_bin, model_path, output_path, quant_type]
    print(f"⚙️  Quantizing model: {model_path}")
    print(f"📦 Output: {output_path} ({quant_type})")

    process = psutil.Process(os.getpid())
    start_ram = process.memory_info().rss / 1024 ** 2
    start_time = time.time()

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"error: quantization failed: {exc}")

    end_time = time.time()
    end_ram = process.memory_info().rss / 1024 ** 2
    model_size = os.path.getsize(output_path) / 1024 ** 2 if os.path.exists(output_path) else 0

    print("\n📊 Quantization Benchmark")
    print(f"Quantization Time: {end_time - start_time:.2f} sec")
    print(f"Peak RAM Used: {max(start_ram, end_ram):.2f} MB")
    print(f"Quantized GGUF Size: {model_size:.2f} MB")
    print(f"✅ Quantized model saved at: {output_path}")
