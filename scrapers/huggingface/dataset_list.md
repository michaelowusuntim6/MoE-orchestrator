# Hugging Face Datasets to Download

Verified against the HF API on 2026-10-05. Sizes are the sum of file sizes
reported by `dataset_info(files_metadata=True)`.

Guards from config.md `## Scrapers`: a dataset is skipped when its total size
exceeds `hf_max_dataset_mb` (5120) or when any single file exceeds
`hf_max_file_mb` (500). Datasets marked SKIP below are correct to keep in the
list — the downloader will report them as skipped decisions, which keeps the
audit trail honest.

## android
# pavelshpagin/SupportBench — 61.1 MB total, 5.8 MB max file — DOWNLOADABLE
pavelshpagin/SupportBench
# DevEscorpion/android-firmware-research — 134.2 GB total, 4.3 GB max file — SKIP (file + dataset too large)
DevEscorpion/android-firmware-research

## linux_kernel
# quguanni/kernel-vuln-dataset — 43.3 MB total, 43.3 MB max file — DOWNLOADABLE
quguanni/kernel-vuln-dataset
# quguanni/kernel-vuln-dataset-full — 1.9 GB total, 1.5 GB max file — SKIP (file too large)
quguanni/kernel-vuln-dataset-full
# xiaoguangwang/syzfix-dataset — 5.1 GB total, 2.9 GB max file — SKIP (file + dataset too large)
xiaoguangwang/syzfix-dataset
# pebblebed/kernel-vuln-dataset — 43.3 MB total, 43.3 MB max file — DOWNLOADABLE
pebblebed/kernel-vuln-dataset

## python
# codeparrot/codeparrot-clean — 12.8 GB total, 248 MB max file — SKIP (dataset too large)
codeparrot/codeparrot-clean

## mql5
# CompilingThings/compile-benchmark — 23.9 MB total, 21.1 MB max file — DOWNLOADABLE
CompilingThings/compile-benchmark

## security
# shahrukh95/OWASP-and-NVD-question-answer-dataset — 7.7 MB total, 7.7 MB max file — DOWNLOADABLE
shahrukh95/OWASP-and-NVD-question-answer-dataset
# shahrukh95/NVD-question-answer-dataset — 6.0 MB total, 6.0 MB max file — DOWNLOADABLE
shahrukh95/NVD-question-answer-dataset

# Removed after verification (404 on 2026-10-05):
#   Quarkslab/AOSP-CVE-dataset

## linux_kernel
# ewedubs/linux-kernel-commits-aireason-instruct — 596.0 MB, max 160.4 MB — PASS
ewedubs/linux-kernel-commits-aireason-instruct
# theelderemo/linux-asm-pairs — 6.6 MB, max 0.4 MB — PASS (asm ↔ source pairs)
theelderemo/linux-asm-pairs
# mjbommar/linux-ioctl-census — 0.4 MB, max 0.1 MB — PASS
mjbommar/linux-ioctl-census
# yeeted-my-bashrc/lkml-domains — 79.4 MB, max 79.4 MB — PASS (LKML thread domains)
yeeted-my-bashrc/lkml-domains
# GAIR/daVinci-kernel-sft — 970.1 MB, max 516.5 MB — STREAM (max file > 500 MB)
GAIR/daVinci-kernel-sft
# anon-sub/syzfix-dataset — 3.0 GB, single 3.0 GB file — STREAM
# SKIPPED 2026-10-05: streaming fails with a dataset-side pyarrow schema error
#   (ArrowInvalid: Failed to parse string '...Z' as a scalar of type timestamp[s]:
#    expected no zone offset). The equivalent data is already covered by
#   xiaoguangwang/syzfix-dataset, which we sampled to 502 MB successfully.

## security
# ayshajavd/code-security-vulnerability-dataset — 131.8 MB, max 105.2 MB — PASS
ayshajavd/code-security-vulnerability-dataset
# lemon42-ai/Code_Vulnerability_Labeled_Dataset — 4.4 MB — PASS
lemon42-ai/Code_Vulnerability_Labeled_Dataset
# jondurbin/bagel-llama-3-v1.0 — 3.9 GB, max 1.9 GB — STREAM
jondurbin/bagel-llama-3-v1.0

## android_security
# srimeenakshiks/Android-Malware-Dataset — 5.1 MB — PASS (1,159 downloads)
srimeenakshiks/Android-Malware-Dataset

## mql5
# AlphaDojo/dojo_forex_kline — 0.1 MB — PASS (15,680 downloads)
AlphaDojo/dojo_forex_kline
# Ehsanrs2/Forex_Factory_Calendar — 68.2 MB — PASS
Ehsanrs2/Forex_Factory_Calendar

## code_review
# ronantakizawa/github-codereview — 652.9 MB, max 99.7 MB — PASS
ronantakizawa/github-codereview
# code-review-bench/code-review-bench — 28.0 MB — PASS
code-review-bench/code-review-bench

## python
# codefuse-ai/CodeExercise-Python-27k — 62.3 MB — PASS (instruction pairs)
codefuse-ai/CodeExercise-Python-27k

# Rejected by the quality gate on 2026-10-05 (recorded, not downloaded):
#   shirman/exploitgym-results   — no_license, no_data_files
#   shirman/exploitgym-answers   — no_license, no_data_files
#   DevEscorpion/android-firmware-research — no_data_files, 125 GB, 4.0 GB single file
#   404: wikimedia/lkml-domains, yeeted-my/bashrc (the real id is yeeted-my-bashrc/lkml-domains)
