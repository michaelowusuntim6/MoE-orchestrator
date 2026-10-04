"""Export a merged HF model to GGUF using llama.cpp's converter."""
import os
import subprocess
import sys
import time

import psutil


def run_export(model_dir, format, output_dir, opset=None, llama_cpp_dir=None):
    if format != "gguf":
        raise ValueError("only 'gguf' export is supported")

    llama_cpp_dir = os.path.expanduser(
        llama_cpp_dir or os.environ.get("LFT_LLAMA_CPP_DIR") or "../llama.cpp"
    )
    os.makedirs(output_dir, exist_ok=True)

    model_name = os.path.basename(model_dir.rstrip("/"))
    output_file = os.path.join(output_dir, f"{model_name}.gguf")

    # 1. Python converter (the supported path in modern llama.cpp)
    script_path = os.path.join(llama_cpp_dir, "convert_hf_to_gguf.py")
    # 2. Compiled C++ converter (only built by some llama.cpp versions)
    binary_path = os.path.join(llama_cpp_dir, "build", "bin", "llama-convert-hf-to-gguf")

    if os.path.isfile(script_path):
        print("📦 Using Python script: convert_hf_to_gguf.py")
        command = [sys.executable, script_path, model_dir, "--outfile", output_file]
    elif os.path.isfile(binary_path):
        print("📦 Using compiled binary: llama-convert-hf-to-gguf")
        command = [binary_path, model_dir, "--outfile", output_file]
    else:
        raise SystemExit(
            f"error: GGUF converter not found under {llama_cpp_dir}. "
            "Set --llama_cpp_dir or LFT_LLAMA_CPP_DIR to a llama.cpp checkout."
        )

    print(f"🚀 Converting model: {model_dir} → {output_file}")
    process = psutil.Process(os.getpid())
    start_ram = process.memory_info().rss / 1024 ** 2
    start_time = time.time()

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"error: GGUF export failed: {exc}")

    end_time = time.time()
    end_ram = process.memory_info().rss / 1024 ** 2
    model_size = os.path.getsize(output_file) / 1024 ** 2 if os.path.exists(output_file) else 0

    print("\n📊 GGUF Export Benchmark")
    print(f"Export Time: {end_time - start_time:.2f} sec")
    print(f"Peak RAM Used: {max(start_ram, end_ram):.2f} MB")
    print(f"GGUF Model Size: {model_size:.2f} MB")
    print(f"✅ GGUF model saved at: {output_file}")
