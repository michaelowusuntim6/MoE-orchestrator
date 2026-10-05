# Master dataset manifest

Generated: 2026-10-05 (expanded same day) · Input for Prompt 3 (HF upload).

Every corpus below is in the canonical Qwen3.5 shape
`{"messages":[{"role","content"}, ...]}` under
`datasets/formatted/<category>/{train,val}.jsonl` with a `manifest.json`.
No content string contains `<|im_start|>` or `<|im_end|>`; the model's chat
template adds them at tokenize time. `--verify-template` passes for all 21
categories.

## Totals

- **30 categories** · **2,987,415 records** · **~10.5 GB** of formatted JSONL
- 12 original categories: **1,989,038**
- 9 categories from the second campaign: **615,330**
- 9 categories from the expansion campaign: **383,047**

## Expansion campaign (2026-10-05, later session)

| category | source | records | train | val | template | trainable at 8192 |
|---|---|---:|---:|---:|---|---|
| `linux_kernel_commits` | `ewedubs/linux-kernel-commits-aireason-instruct` | 37,770 | 37,031 | 739 | PASS | yes (0% trunc) |
| `linux_kernel_assembly` | `theelderemo/linux-asm-pairs` | 4,203 | 4,129 | 74 | PASS | yes (1.0%) |
| `linux_kernel_ioctl` | `mjbommar/linux-ioctl-census` | 1,289 | 1,261 | 28 | PASS | yes (0%) |
| `kernel_davinci` | `GAIR/daVinci-kernel-sft` (500 MB stream) | 5,498 | 5,372 | 126 | PASS | **no — 100% truncation** |
| `code_review` | `ronantakizawa/github-codereview` | 233,235 | 228,452 | 4,783 | PASS | yes (2.5%) |
| `security_expanded` | `ayshajavd/…`, `lemon42-ai/…`, `jondurbin/bagel-llama-3-v1.0` (500 MB stream) | 8,480 | 8,323 | 157 | PASS | yes (0%) |
| `android_malware` | `srimeenakshiks/Android-Malware-Dataset` | 7,489 | 7,336 | 153 | PASS | yes (0%) |
| `forex_calendar` | `Ehsanrs2/Forex_Factory_Calendar` | 83,427 | 81,793 | 1,634 | PASS | yes (0%) |
| `mql5_expanded` | 52 newly cloned MQL5 GitHub repos | 1,656 | 1,618 | 38 | PASS | yes (13.5%) |

`kernel_davinci` caveat: the release contains long agentic Triton-kernel
sessions; at `max_length = 8192` 100% of sampled records truncate and 99.5%
end with an all-zero assistant mask. The corpus is formatted and correct, but
training it needs a larger context on a GPU (see `docs/TRAINING_RUNBOOK.md`).

### Expansion campaign sources

Downloaded (13 ok / 12 skipped / 0 failed, 2.4 GB) plus three 500 MB streamed
samples (daVinci 8,879 raw records, bagel 248,833). Quality gate rejected
`shirman/exploitgym-results` and `shirman/exploitgym-answers`
(no license, no data files); `anon-sub/syzfix-dataset` streamed-failed on a
dataset-side pyarrow timestamp schema error and is already covered by
`xiaoguangwang/syzfix-dataset`.

GitHub: 56 MQL5 repos in the list, 52 newly cloned from a search that
examined 107 candidates (54 passed the gate; kernel/ROM repos stay excluded by
policy). Cloned total 267.9 MB.

`yeeted-my-bashrc/lkml-domains` was downloaded but **not formatted**: the
release contains a single `domain` column (email domains, no thread text), so
it cannot produce instruction pairs.

## New categories (this campaign)

| category | source | records | train | val | size | template |
|---|---|---:|---:|---:|---:|---|
| `supportbench_lineageos` | `pavelshpagin/SupportBench` → `lineageos.json` (Telegram reply threads) | 4,741 | 4,637 | 104 | 1.4 MB | PASS |
| `kernel_vuln` | `quguanni/kernel-vuln-dataset` + `pebblebed/kernel-vuln-dataset` (CSV, 22 columns) | 241,116 | 236,235 | 4,881 | 89.7 MB | PASS |
| `kernel_syzfix_sample` | 500 MB stream of `xiaoguangwang/syzfix-dataset` | 1,918 | 1,880 | 38 | 13.1 MB | PASS |
| `kernel_vuln_full_sample` | 500 MB stream of `quguanni/kernel-vuln-dataset-full` (git commits + `diff_raw`) | 100,506 | 98,542 | 1,964 | 396.0 MB | PASS |
| `mql5_benchmark` | `CompilingThings/compile-benchmark` (prompts + compile verdicts) | 184 | 179 | 5 | 0.2 MB | PASS |
| `mql5_repos` | 4 GitHub MQL5 repos (`.mq5`/`.mqh`/README) | 1,057 | 1,041 | 16 | 21.1 MB | PASS |
| `security_qa` | `shahrukh95/OWASP-and-NVD-…` + `shahrukh95/NVD-…` (CSV Q/A) | 22,953 | 22,539 | 414 | 10.9 MB | PASS |
| `lineageos_tree` | local LineageOS 23.2 walk (200k files catalogued) | 194,832 | 190,827 | 4,005 | 1,510.3 MB | PASS |
| `python_codeparrot_sample` | 500 MB stream of `codeparrot/codeparrot-clean` | 48,023 | 47,048 | 975 | 418.4 MB | PASS |

## Existing categories (unchanged, from the first campaign)

| category | records | size |
|---|---:|---:|
| agent_tool | 676,399 | 2,807.7 MB |
| android | 187,466 | 99.4 MB |
| coding_debug | 416,548 | 1,613.6 MB |
| cpp | 34,131 | 30.2 MB |
| generated_lineageos | 3,227 | 8.2 MB |
| generated_mql5 | 3,101 | 9.1 MB |
| kernel | 2,500 | 17.1 MB |
| linux | 19,740 | 19.1 MB |
| python | 151,336 | 121.9 MB |
| reasoning_algorithms | 210,340 | 550.8 MB |
| security_data | 170,290 | 410.2 MB |
| uncategorized | 113,960 | 113.8 MB |

## Hugging Face downloads

| dataset | result | detail |
|---|---|---|
| `pavelshpagin/SupportBench` | downloaded | 61.1 MB, 42 files |
| `quguanni/kernel-vuln-dataset` | downloaded | 43.3 MB |
| `pebblebed/kernel-vuln-dataset` | downloaded | 43.3 MB (same content as quguanni — deduped in formatting) |
| `CompilingThings/compile-benchmark` | downloaded | 23.9 MB |
| `shahrukh95/OWASP-and-NVD-question-answer-dataset` | downloaded | 7.7 MB |
| `shahrukh95/NVD-question-answer-dataset` | downloaded | 6.0 MB |
| `codeparrot/codeparrot-clean` | **streamed** | 500.0 MB sampled of 12.8 GB → 48,905 raw records |
| `xiaoguangwang/syzfix-dataset` | **streamed** | 502.6 MB sampled of 5.1 GB → 1,923 raw records |
| `quguanni/kernel-vuln-dataset-full` | **streamed** | 500.0 MB sampled of 1.9 GB → 101,023 raw records |
| `DevEscorpion/android-firmware-research` | **skipped** | 134 GB total, 4.3 GB single file — exceeds the 500 MB per-file ceiling and is not streamable |

Downloaded total: **176.7 MB** on disk plus **1.5 GB** of streamed samples.

## GitHub scrapes (MQL5 only)

| repo | size | files removed |
|---|---:|---:|
| `homayoun-asghari/mql5-expert-advisors` | 0.1 MB | 0 |
| `geraked/metatrader5` | 10.2 MB | 0 |
| `EA31337/EA31337-classes` | 9.5 MB | 0 |
| `Pierre8r/All-MQL5-code` | 2.1 MB | 0 |

Total 51.4 MB, 359 `.mq5` and 1,077 `.mqh` files, no `_truncated.json`
created (nothing exceeded 500 MB). **Kernel repositories were deliberately
excluded** — the local LineageOS tree supplies kernel source instead.

## LineageOS tree walk

200,000 files catalogued, 2.19 GB, 23 files skipped (>10 MB).
50,686 device-specific files (`device/samsung/a04s`,
`kernel/samsung/exynos850`, `vendor/samsung/a04s`) are ordered first.
Top directories: `external` 110,603 · `kernel` 50,437 · `cts` 17,597 ·
`device` 6,910 · `art` 5,316 · `bionic` 2,918 · `development` 2,797 ·
`build` 2,292.

## Sampling and truncation policy

Three datasets exceeded the 500 MB per-file ceiling but are sharded and
streamable, so they were sampled to 500 MB each via
`datasets.load_dataset(..., streaming=True)`; the original sizes and the
sample sizes are recorded in each `_sample.json`. The one dataset with a
monolithic 4.3 GB file (`DevEscorpion/android-firmware-research`) was skipped
rather than partially downloaded.

## Ready for upload (Prompt 3)

All 21 categories produce a non-empty `train.jsonl`. The 9 new categories are
the upload candidates for this campaign:

`supportbench_lineageos`, `kernel_vuln`, `kernel_syzfix_sample`,
`kernel_vuln_full_sample`, `mql5_benchmark`, `mql5_repos`, `security_qa`,
`lineageos_tree`, `python_codeparrot_sample`.

Note on `mql5_benchmark`: the public release contains the prompts and the
compile verdicts but **withholds the model completions** (`private_outputs` in
its own `PROJECTION_REPORT.json`). The assistant turn therefore carries the
release's own compile verdict rather than generated MQL5 code. Real MQL5
source comes from `mql5_repos`.

## Failures

None. No category failed to format and no download failed.
