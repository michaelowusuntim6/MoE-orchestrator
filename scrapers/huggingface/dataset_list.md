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
