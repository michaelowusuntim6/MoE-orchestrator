#!/usr/bin/env bash
# Upload every formatted corpus to Hugging Face, smallest first so most
# datasets land even if the session runs out of wall clock.
# One at a time (no parallelism) to stay well inside Hub rate limits.
set -u
cd "$(dirname "$0")/../.." || exit 1

# folder:repo-name, ordered by ascending size
MAP=(
  "mql5_benchmark:mql5-compile-benchmark"
  "linux_kernel_ioctl:linux-kernel-ioctl-qwen35"
  "supportbench_lineageos:lineageos-support-qwen35"
  "security_expanded:security-expanded-qwen35"
  "android_malware:android-malware-qwen35"
  "generated_lineageos:lineageos-generated-qwen35"
  "generated_mql5:mql5-generated-qwen35"
  "security_qa:security-qa-qwen35"
  "kernel_syzfix_sample:kernel-syzfix-qwen35"
  "kernel:kernel-qwen35"
  "linux_kernel_assembly:linux-kernel-asm-qwen35"
  "linux:linux-qwen35"
  "mql5_repos:mql5-repos-qwen35"
  "mql5_expanded:mql5-expanded-qwen35"
  "cpp:cpp-qwen35"
  "forex_calendar:forex-calendar-qwen35"
  "kernel_vuln:kernel-vuln-qwen35"
  "android:android-qwen35"
  "uncategorized:uncategorized-qwen35"
  "python:python-qwen35"
  "linux_kernel_commits:linux-kernel-commits-qwen35"
  "kernel_davinci:kernel-davinci-qwen35"
  "kernel_vuln_full_sample:kernel-vuln-full-qwen35"
  "security_data:security-qwen35"
  "python_codeparrot_sample:python-codeparrot-qwen35"
  "reasoning_algorithms:reasoning-qwen35"
  "code_review:code-review-qwen35"
  "lineageos_tree:lineageos-tree-qwen35"
  "coding_debug:debug-qwen35"
  "agent_tool:agent-tool-qwen35"
)

LOG="scrapers/logs/hf_upload.log"
mkdir -p scrapers/logs

ok=0
fail=0
failed=()

for entry in "${MAP[@]}"; do
  folder="${entry%%:*}"
  name="${entry#*:}"
  path="datasets/formatted/$folder"
  start=$(date +%s)
  echo "=== Uploading $folder -> $name ($(date -u +%H:%M:%S)) ===" | tee -a "$LOG"
  if ./venv-inference/bin/python scrapers/huggingface/hf_uploader.py \
       --name "$name" \
       --path "$path" \
       --commit-message "v1 - $folder corpus for Qwen3.5" >> "$LOG" 2>&1; then
    ok=$((ok+1))
    echo "OK   $folder -> https://huggingface.co/datasets/michaelowusuntim6/$name ($(( $(date +%s) - start ))s)" | tee -a "$LOG"
  else
    fail=$((fail+1))
    failed+=("$folder")
    echo "FAIL $folder -> $name" | tee -a "$LOG"
  fi
done

echo "=== Done: $ok ok, $fail failed ===" | tee -a "$LOG"
if [ "$fail" -gt 0 ]; then
  printf 'failed: %s\n' "${failed[*]}" | tee -a "$LOG"
  exit 1
fi
exit 0
