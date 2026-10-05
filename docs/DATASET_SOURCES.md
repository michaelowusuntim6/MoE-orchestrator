# Dataset sources

## Expansion campaign (2026-10-05, later session)

### Hugging Face — passed the quality gate and downloaded (13)

| category | dataset | size | gate |
|---|---|---:|---|
| linux_kernel | `ewedubs/linux-kernel-commits-aireason-instruct` | 596.0 MB | PASS |
| linux_kernel | `theelderemo/linux-asm-pairs` | 6.6 MB | PASS |
| linux_kernel | `mjbommar/linux-ioctl-census` | 0.4 MB | PASS |
| linux_kernel | `yeeted-my-bashrc/lkml-domains` | 79.4 MB | PASS (not formattable — see below) |
| linux_kernel | `GAIR/daVinci-kernel-sft` | 970.1 MB | PASS → streamed 500 MB |
| security | `ayshajavd/code-security-vulnerability-dataset` | 131.8 MB | PASS |
| security | `lemon42-ai/Code_Vulnerability_Labeled_Dataset` | 4.4 MB | PASS |
| security | `jondurbin/bagel-llama-3-v1.0` | 3.9 GB | PASS → streamed 500 MB |
| android_security | `srimeenakshiks/Android-Malware-Dataset` | 5.1 MB | PASS |
| mql5 | `AlphaDojo/dojo_forex_kline` | 0.1 MB | PASS |
| mql5 | `Ehsanrs2/Forex_Factory_Calendar` | 68.2 MB | PASS |
| code_review | `ronantakizawa/github-codereview` | 652.9 MB | PASS |
| code_review | `code-review-bench/code-review-bench` | 28.0 MB | PASS |
| python | `codefuse-ai/CodeExercise-Python-27k` | 62.3 MB | PASS |

### Rejected by the quality gate (not downloaded)

| dataset | reason |
|---|---|
| `shirman/exploitgym-results` | no_license, no_data_files |
| `shirman/exploitgym-answers` | no_license, no_data_files |
| `DevEscorpion/android-firmware-research` | no_data_files, 125 GB, 4.0 GB single file |
| `anon-sub/syzfix-dataset` | stream-failed (pyarrow timestamp schema); covered by `xiaoguangwang/syzfix-dataset` |
| `wikimedia/lkml-domains`, `yeeted-my/bashrc` | 404 (the real id is `yeeted-my-bashrc/lkml-domains`) |

### GitHub — 107 candidates from 8 search queries, 54 passing, 52 newly cloned

Search topics: `mql5`, `expert-advisor`, `forex-robot`, `metatrader5`,
`algorithmic-trading` (all `language:MQL5`, stars > 5), plus `android-kernel`,
`lineageos` and `android-rom` which are **reported but never cloned** by
project policy. Clone total 267.9 MB; the repo list now holds 56 MQL5 repos.

`yeeted-my-bashrc/lkml-domains` note: the release contains a single `domain`
column (LKML posters' email domains). There is no thread text, so it cannot
produce instruction pairs and is deliberately not formatted.

## Acquisition result (2026-10-05, Prompt 2)

All sources below were acquired. Nothing was uploaded.

| source | disposition | actual |
|---|---|---|
| `pavelshpagin/SupportBench` | downloaded | 61.1 MB |
| `quguanni/kernel-vuln-dataset` | downloaded | 43.3 MB |
| `pebblebed/kernel-vuln-dataset` | downloaded | 43.3 MB (duplicate content of quguanni) |
| `CompilingThings/compile-benchmark` | downloaded | 23.9 MB |
| `shahrukh95/OWASP-and-NVD-question-answer-dataset` | downloaded | 7.7 MB |
| `shahrukh95/NVD-question-answer-dataset` | downloaded | 6.0 MB |
| `codeparrot/codeparrot-clean` | **streamed sample** | 500.0 MB of 12.8 GB → 48,905 records |
| `xiaoguangwang/syzfix-dataset` | **streamed sample** | 502.6 MB of 5.1 GB → 1,923 records |
| `quguanni/kernel-vuln-dataset-full` | **streamed sample** | 500.0 MB of 1.9 GB → 101,023 records |
| `DevEscorpion/android-firmware-research` | **skipped** | 134 GB total with a monolithic 4.3 GB file — not streamable |
| 4 MQL5 GitHub repos | cloned | 51.4 MB → 359 `.mq5`, 1,077 `.mqh` |
| Local LineageOS 23.2 tree | walked (read-only) | 200,000 files, 2.19 GB, 50,686 device-priority |
| `LineageOS/android_kernel_samsung_exynos850`, `samsungexynos850/local_manifests`, `lesdieuxx/android_kernel_a047f_resukisu` | **excluded** | policy: kernel repositories are not cloned; the local tree covers kernel source |

Formatted output: 9 new categories, **615,330 records**, all template-verified
and ≤2.5% truncated at `max_length = 8192`. Full detail in
`datasets/_master_manifest.md`.

Note on `mql5_benchmark`: the public release ships prompts plus compile
verdicts and **withholds completions** (its own `PROJECTION_REPORT.json` lists
`private_outputs`/`withheld_fields`). The assistant turn therefore carries the
release's verdict sentence rather than generated MQL5 code.

Verified against the Hugging Face and GitHub APIs on **2026-10-05**. Sizes are
the sum of the files the API reports for the default revision. Nothing in this
table has been downloaded yet.

Guards (config.md `## Scrapers`): no single file may exceed **500 MB**
(`hf_max_file_mb`, `github_max_file_mb`); dataset total ≤ `hf_max_dataset_mb`
(5120 MB), repo total ≤ `github_max_repo_mb` (2048 MB). Entries marked
**SKIP** are kept in the lists on purpose so the downloader logs the decision
instead of silently dropping the source.

## Hugging Face datasets — `scrapers/huggingface/dataset_list.md`

| category | dataset | total | largest file | status |
|---|---|---:|---:|---|
| android | `pavelshpagin/SupportBench` | 61.1 MB | 5.8 MB | DOWNLOADABLE |
| android | `DevEscorpion/android-firmware-research` | 134.2 GB | 4.3 GB | SKIP (file + dataset too large) |
| linux_kernel | `quguanni/kernel-vuln-dataset` | 43.3 MB | 43.3 MB | DOWNLOADABLE |
| linux_kernel | `quguanni/kernel-vuln-dataset-full` | 1.9 GB | 1.5 GB | SKIP (file too large) |
| linux_kernel | `xiaoguangwang/syzfix-dataset` | 5.1 GB | 2.9 GB | SKIP (file + dataset too large) |
| linux_kernel | `pebblebed/kernel-vuln-dataset` | 43.3 MB | 43.3 MB | DOWNLOADABLE |
| python | `codeparrot/codeparrot-clean` | 12.8 GB | 248 MB | SKIP (dataset too large) |
| mql5 | `CompilingThings/compile-benchmark` | 23.9 MB | 21.1 MB | DOWNLOADABLE |
| security | `shahrukh95/OWASP-and-NVD-question-answer-dataset` | 7.7 MB | 7.7 MB | DOWNLOADABLE |
| security | `shahrukh95/NVD-question-answer-dataset` | 6.0 MB | 6.0 MB | DOWNLOADABLE |

Removed after verification (404): `Quarkslab/AOSP-CVE-dataset`.

These are the **curated** sources. `hf_search.py` additionally discovers
datasets by keyword (`lineageos`, `aosp`, `android-kernel`, `exynos850`,
`mql5`, `metatrader`, `forex`, `linux-kernel`, `kernel-vuln`,
`kernel-security`, `android-firmware`, `android-security`, `codeparrot`,
`python-code`, `cpp-code`) and writes the candidates, with sizes and skip
reasons, to `scrapers/logs/hf_search_results.json`.

## GitHub repositories — `scrapers/github/repo_list.md`

| category | repo | size | notes |
|---|---|---:|---|
| mql5 | `homayoun-asghari/mql5-expert-advisors` | 0.1 MB | DOWNLOADABLE |
| mql5 | `geraked/metatrader5` | 10.2 MB | DOWNLOADABLE |
| mql5 | `EA31337/EA31337-classes` | 9.5 MB | DOWNLOADABLE |
| mql5 | `Pierre8r/All-MQL5-code` | 2.1 MB | DOWNLOADABLE |
| android_kernel | `LineageOS/android_kernel_samsung_exynos850` | 2201 MB | SKIP at the 2048 MB cap — pass `--allow-large` |
| android_kernel | `samsungexynos850/local_manifests` | 0.0 MB | DOWNLOADABLE |
| android_kernel | `lesdieuxx/android_kernel_a047f_resukisu` | 218 MB | DOWNLOADABLE |

All seven exist; no 404s. None are forks; none are archived.

## Local LineageOS tree — `scrapers/lineageos/lineageos_walker.py`

`/run/media/mike/Android/lineage-23.2/` (read-only). A dry run matched
**200,000** files (2.0 GB) — the configured `lineageos_max_files` cap — of
which **50,686** are device-specific
(`device/samsung/a04s`, `kernel/samsung/exynos850`, `vendor/samsung/a04s`).
Top extensions: `.h` 59,837, `.c` 47,667, `.java` 44,385, `.cpp` 23,895,
`.py` 8,656, `.bp` 5,659, `.te` 4,049, `.sh` 2,343. 23 files were larger
than `lineageos_max_file_mb` (10 MB) and were skipped.

The tree contributes to the `android` and `linux_kernel` experts; the
priority ordering guarantees the A04s/Exynos850 material survives any
truncation.

## Field coverage

| field of interest | HF | GitHub | local tree |
|---|---|---|---|
| Android / LineageOS ROM | SupportBench | `android_kernel_*`, `local_manifests` | device/samsung/a04s, vendor/samsung/a04s |
| Exynos850 kernel | kernel-vuln datasets | `android_kernel_samsung_exynos850` | kernel/samsung/exynos850 |
| MQL5 / trading | compile-benchmark | 4 MQL5 repos | — |
| Coding / debugging | codeparrot (skip: too large) | kernel + MQL5 code | 200k source files |
| Security | NVD + OWASP Q&A | — | `.te` SELinux policy, security dirs |
