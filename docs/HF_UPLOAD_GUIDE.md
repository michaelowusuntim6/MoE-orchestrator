# Hugging Face upload guide

All 30 formatted corpora are published under **michaelowusuntim6**:
https://huggingface.co/michaelowusuntim6

Every dataset ships `train.jsonl`, `val.jsonl`, `manifest.json` and a
`README.md` card with YAML frontmatter, source attribution and licence.

## Android / LineageOS

### Android / LineageOS Support Corpus (`android-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/android-qwen35
- **Records:** 187,466 (train: 183,647, val: 3,819)
- **Source:** ReallyHelpfulClean.md curated list (mteb, HarrytheOrange, ckg, giggiovpg, OfficerChul, soongfs, GreenNode); HarrytheOrange/parsed_AndroidControl; Android Kotlin/Compose sources
- **License:** mixed (per-source; see docs/DATASET_SOURCES.md)
- **Domain:** Android / LineageOS
- **Expert target:** `android`

### LineageOS 23.2 Source Tree (`lineageos-tree-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/lineageos-tree-qwen35
- **Records:** 194,832 (train: 190,827, val: 4,005)
- **Source:** Local LineageOS 23.2 tree (AOSP fork) - 200,000 files walked read-only, ordered device-first for Galaxy A04s / Exynos850
- **License:** AOSP/LineageOS upstream licences (Apache-2.0 and per-project)
- **Domain:** Android / LineageOS
- **Expert target:** `android`

### LineageOS Support Dialogues (`lineageos-support-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/lineageos-support-qwen35
- **Records:** 4,741 (train: 4,637, val: 104)
- **Source:** pavelshpagin/SupportBench - lineageos.json (t.me/Lineageos_group), Apache-2.0
- **License:** apache-2.0
- **Domain:** Android / LineageOS
- **Expert target:** `android`

### Android Malware Classification (`android-malware-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/android-malware-qwen35
- **Records:** 7,489 (train: 7,336, val: 153)
- **Source:** srimeenakshiks/Android-Malware-Dataset - MIT
- **License:** mit
- **Domain:** Android / LineageOS
- **Expert target:** `security`

### Generated LineageOS Q&A (`lineageos-generated-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/lineageos-generated-qwen35
- **Records:** 3,227 (train: 3,171, val: 56)
- **Source:** Project-generated 11_lineageos.jsonl (3,227 examples) authored for this project
- **License:** project-generated
- **Domain:** Android / LineageOS
- **Expert target:** `android`

## Linux Kernel

### Linux Kernel Q&A (`kernel-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/kernel-qwen35
- **Records:** 2,500 (train: 2,452, val: 48)
- **Source:** beatsprom/autonomous-linux-kernel-ebpf-xdp-suite, from the ReallyHelpfulClean.md curated list
- **License:** mixed
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### Linux Shell and CLI Corpus (`linux-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/linux-qwen35
- **Records:** 19,740 (train: 19,357, val: 383)
- **Source:** b-mc2/cli-commands-explained; NickIBrody/linux-shell-corpus-ru-en; rajivmehtapy/shell-script-specialist-dataset
- **License:** mixed
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### Linux Kernel Vulnerability Commits (`kernel-vuln-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/kernel-vuln-qwen35
- **Records:** 241,116 (train: 236,235, val: 4,881)
- **Source:** quguanni/kernel-vuln-dataset; pebblebed/kernel-vuln-dataset
- **License:** mixed
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### syzfix Kernel Crash Fixes (sample) (`kernel-syzfix-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/kernel-syzfix-qwen35
- **Records:** 1,918 (train: 1,880, val: 38)
- **Source:** xiaoguangwang/syzfix-dataset - 500 MB streamed sample of 5.1 GB
- **License:** mixed
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### Linux Kernel Commit Diffs (sample) (`kernel-vuln-full-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/kernel-vuln-full-qwen35
- **Records:** 100,506 (train: 98,542, val: 1,964)
- **Source:** quguanni/kernel-vuln-dataset-full - 500 MB streamed sample of 1.9 GB
- **License:** mixed
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### Linux Kernel Commit Reasoning (`linux-kernel-commits-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/linux-kernel-commits-qwen35
- **Records:** 37,770 (train: 37,031, val: 739)
- **Source:** ewedubs/linux-kernel-commits-aireason-instruct - Apache-2.0
- **License:** apache-2.0
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### Linux Kernel Assembly Pairs (`linux-kernel-asm-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/linux-kernel-asm-qwen35
- **Records:** 4,203 (train: 4,129, val: 74)
- **Source:** theelderemo/linux-asm-pairs - GPL-2.0
- **License:** gpl-2.0
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### Linux ioctl Census (`linux-kernel-ioctl-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/linux-kernel-ioctl-qwen35
- **Records:** 1,289 (train: 1,261, val: 28)
- **Source:** mjbommar/linux-ioctl-census - CC-BY-4.0
- **License:** cc-by-4.0
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`

### daVinci Triton Kernel Optimization (`kernel-davinci-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/kernel-davinci-qwen35
- **Records:** 5,498 (train: 5,372, val: 126)
- **Source:** GAIR/daVinci-kernel-sft - 500 MB streamed sample of 970 MB
- **License:** apache-2.0
- **Domain:** Linux Kernel
- **Expert target:** `linux_kernel`
- **Caveats:** GPU-only: 100% truncation at max_length=8192; needs a GPU with context > 8192.

## MQL5 / Forex

### MQL5 Expert Advisor Source (`mql5-repos-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/mql5-repos-qwen35
- **Records:** 1,057 (train: 1,041, val: 16)
- **Source:** homayoun-asghari/mql5-expert-advisors; geraked/metatrader5; EA31337/EA31337-classes …
- **License:** mixed (per-repo; mostly MIT/GPL-3.0)
- **Domain:** MQL5 / Forex
- **Expert target:** `mql5_optional`

### MQL5 Expert Advisor Source (expanded) (`mql5-expanded-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/mql5-expanded-qwen35
- **Records:** 1,656 (train: 1,618, val: 38)
- **Source:** 52 additional MQL5 repositories discovered via the GitHub search API (stars > 5, licence required); see scrapers/github/repo_list.md
- **License:** mixed (per-repo)
- **Domain:** MQL5 / Forex
- **Expert target:** `mql5_optional`

### MQL5 Compile-Success Benchmark (`mql5-compile-benchmark`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/mql5-compile-benchmark
- **Records:** 184 (train: 179, val: 5)
- **Source:** CompilingThings/compile-benchmark
- **License:** see source repository
- **Domain:** MQL5 / Forex
- **Expert target:** `mql5_optional`
- **Caveats:** Evaluation set, not training data: the release withholds completions; the assistant turn is the compile verdict.

### Forex Economic Calendar (`forex-calendar-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/forex-calendar-qwen35
- **Records:** 83,427 (train: 81,793, val: 1,634)
- **Source:** Ehsanrs2/Forex_Factory_Calendar - MIT
- **License:** mit
- **Domain:** MQL5 / Forex
- **Expert target:** `mql5_optional`

### Generated MQL5 Q&A (`mql5-generated-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/mql5-generated-qwen35
- **Records:** 3,101 (train: 3,032, val: 69)
- **Source:** Project-generated 14_mql5.jsonl (3,101 examples) authored for this project
- **License:** project-generated
- **Domain:** MQL5 / Forex
- **Expert target:** `mql5_optional`

## Coding / Debug / Review

### Python Code Corpus (`python-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/python-qwen35
- **Records:** 151,336 (train: 148,247, val: 3,089)
- **Source:** NickIBrody/python-code-instructions-85k; ronantakizawa/python-code-instructions-japanese; flytech/llama-python-codes-30k …
- **License:** mixed
- **Domain:** Coding / Debug / Review
- **Expert target:** `code_python`

### C / C++ Code Corpus (`cpp-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/cpp-qwen35
- **Records:** 34,131 (train: 33,419, val: 712)
- **Source:** shareAI/CodeChat; Mxode/StackOverflow-QA-C-Language-40k; dumb-dev/cpp-10k …
- **License:** mixed
- **Domain:** Coding / Debug / Review
- **Expert target:** `code_cpp`

### Code Review Corpus (`code-review-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/code-review-qwen35
- **Records:** 233,235 (train: 228,452, val: 4,783)
- **Source:** ronantakizawa/github-codereview - Other; code-review-bench/code-review-bench - CC-BY-4.0
- **License:** mixed (other / cc-by-4.0)
- **Domain:** Coding / Debug / Review
- **Expert target:** `debug_review`

### Coding and Debugging Traces (`debug-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/debug-qwen35
- **Records:** 416,548 (train: 408,372, val: 8,176)
- **Source:** greghavens/kimi-k3-coding-and-debugging-traces; JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified; and 27 more datasets from the curated list
- **License:** mixed
- **Domain:** Coding / Debug / Review
- **Expert target:** `debug_review`

### CodeParrot Clean Python (sample) (`python-codeparrot-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/python-codeparrot-qwen35
- **Records:** 48,023 (train: 47,048, val: 975)
- **Source:** codeparrot/codeparrot-clean - 500 MB streamed sample of 12.8 GB; the per-file licence field is preserved in the text
- **License:** per-file (mostly MIT/Apache-2.0)
- **Domain:** Coding / Debug / Review
- **Expert target:** `code_python`

## Security

### Security and AppSec Corpus (`security-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/security-qwen35
- **Records:** 170,290 (train: 166,885, val: 3,405)
- **Source:** Trendyol/Trendyol-Cybersecurity-Instruction-Tuning-Dataset; AlicanKiraz0/Cybersecurity-Dataset-Heimdall-v1.1; mlfoundations-dev/stackexchange_security and 11 more
- **License:** mixed
- **Domain:** Security
- **Expert target:** `security`

### NVD and OWASP Question Answering (`security-qa-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/security-qa-qwen35
- **Records:** 22,953 (train: 22,539, val: 414)
- **Source:** shahrukh95/OWASP-and-NVD-question-answer-dataset; shahrukh95/NVD-question-answer-dataset
- **License:** see source datasets
- **Domain:** Security
- **Expert target:** `security`

### Secure Coding and Vulnerability Fixes (`security-expanded-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/security-expanded-qwen35
- **Records:** 8,480 (train: 8,323, val: 157)
- **Source:** ayshajavd/code-security-vulnerability-dataset - Apache-2.0; lemon42-ai/Code_Vulnerability_Labeled_Dataset - Apache-2.0; jondurbin/bagel-llama-3-v1.0 - Apache-2.0 (500 MB sample)
- **License:** apache-2.0 (mixed)
- **Domain:** Security
- **Expert target:** `security`

## Agent / Reasoning / Misc

### Agentic Tool-Use Corpus (`agent-tool-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/agent-tool-qwen35
- **Records:** 676,399 (train: 663,056, val: 13,343)
- **Source:** NousResearch/hermes-function-calling-v1; allenai/Dolci-Instruct-SFT-Tool-Use-SA; Mustafaege/qwen3.5-toolcalling-v1 and 45 more
- **License:** mixed
- **Domain:** Agent / Reasoning / Misc
- **Expert target:** `agent_tool`

### Reasoning and Algorithms (`reasoning-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/reasoning-qwen35
- **Records:** 210,340 (train: 206,036, val: 4,304)
- **Source:** 0x22almostEvil/reasoning-gsm-qna-oa; HuggingFaceTB/CoT_Reasoning_Bushcraft_Survival; Conversational-Reasoning/Topical-Chat and 25 more
- **License:** mixed
- **Domain:** Agent / Reasoning / Misc
- **Expert target:** `reasoning`

### Uncategorised Grab Bag (`uncategorized-qwen35`)

- **URL:** https://huggingface.co/datasets/michaelowusuntim6/uncategorized-qwen35
- **Records:** 113,960 (train: 111,651, val: 2,309)
- **Source:** seablue/DiDi_GAIA_dataset_jsonl; Chinese-Vicuna/instruct_chat_50k.jsonl; ostapeno/qa-platy-* (4 datasets that matched no expert category)
- **License:** mixed
- **Domain:** Agent / Reasoning / Misc
- **Expert target:** `unassigned`
- **Caveats:** Grab bag, not assigned to a specific expert.

## How to load

```python
from datasets import load_dataset
ds = load_dataset("michaelowusuntim6/code-review-qwen35", split="train")
print(ds[0]["messages"])
```

## How to fine-tune on Colab

Open [`notebooks/qwen35_0.8b_colab.ipynb`](../notebooks/qwen35_0.8b_colab.ipynb)
(or the Kaggle variant for T4 x2) and set `DATASET_NAME` to any repo above.

## License summary

Distinct licence values across the 30 cards:

- AOSP/LineageOS upstream licences (Apache-2.0 and per-project)
- apache-2.0
- apache-2.0 (mixed)
- cc-by-4.0
- gpl-2.0
- mit
- mixed
- mixed (other / cc-by-4.0)
- mixed (per-repo)
- mixed (per-repo; mostly MIT/GPL-3.0)
- mixed (per-source; see docs/DATASET_SOURCES.md)
- per-file (mostly MIT/Apache-2.0)
- project-generated
- see source datasets
- see source repository

Where a card says `other` in its frontmatter, the body lists the
per-source licences (these are mixed-source aggregations).

**Total published records: 2,987,415**
