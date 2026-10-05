#!/usr/bin/env python3
"""Write a README.md dataset card into every datasets/formatted/<category>/.

The card carries YAML frontmatter, source attribution, license, format,
splits, a usage example and any category caveat. Cards are written before
upload so the Hub always gets attribution with the data.

    ./venv-inference/bin/python scrapers/huggingface/make_cards.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import load_config  # noqa: E402

# Hugging Face validates the frontmatter `license` against its own identifier
# list, so mixed/descriptive values must be collapsed to `other`. The detailed
# wording stays in the body's License section.
VALID_FM_LICENSES = {
    "apache-2.0", "mit", "cc-by-4.0", "cc-by-sa-4.0", "cc-by-nc-4.0",
    "cc-by-nc-sa-4.0", "gpl-2.0", "gpl-3.0", "lgpl-2.1", "lgpl-3.0",
    "bsd-2-clause", "bsd-3-clause", "mpl-2.0", "openrail", "other",
}


def frontmatter_license(license_id: str) -> str:
    value = (license_id or "").strip().lower()
    if value in VALID_FM_LICENSES:
        return value
    for candidate in VALID_FM_LICENSES:
        if value.startswith(candidate):
            return candidate
    return "other"

# category -> (human name, repo name, domain tags, sources, license, expert)
META = {
    "android": ("Android / LineageOS Support Corpus", "android-qwen35",
                ["android", "lineageos"],
                ["ReallyHelpfulClean.md curated list (mteb, HarrytheOrange, ckg, "
                 "giggiovpg, OfficerChul, soongfs, GreenNode)",
                 "HarrytheOrange/parsed_AndroidControl",
                 "Android Kotlin/Compose sources"],
                "mixed (per-source; see docs/DATASET_SOURCES.md)", "android"),
    "lineageos_tree": ("LineageOS 23.2 Source Tree", "lineageos-tree-qwen35",
                       ["android", "lineageos", "aosp", "source-code"],
                       ["Local LineageOS 23.2 tree (AOSP fork) - 200,000 files walked "
                        "read-only, ordered device-first for Galaxy A04s / Exynos850"],
                       "AOSP/LineageOS upstream licences (Apache-2.0 and per-project)",
                       "android"),
    "supportbench_lineageos": ("LineageOS Support Dialogues", "lineageos-support-qwen35",
                               ["android", "lineageos", "support", "qa"],
                               ["pavelshpagin/SupportBench - lineageos.json "
                                "(t.me/Lineageos_group), Apache-2.0"],
                               "apache-2.0", "android"),
    "android_malware": ("Android Malware Classification", "android-malware-qwen35",
                        ["android", "security", "malware"],
                        ["srimeenakshiks/Android-Malware-Dataset - MIT"],
                        "mit", "security"),
    "generated_lineageos": ("Generated LineageOS Q&A", "lineageos-generated-qwen35",
                            ["android", "lineageos", "generated"],
                            ["Project-generated 11_lineageos.jsonl (3,227 examples) "
                             "authored for this project"],
                            "project-generated", "android"),
    "kernel": ("Linux Kernel Q&A", "kernel-qwen35", ["linux", "kernel"],
               ["beatsprom/autonomous-linux-kernel-ebpf-xdp-suite, from the "
                "ReallyHelpfulClean.md curated list"], "mixed", "linux_kernel"),
    "linux": ("Linux Shell and CLI Corpus", "linux-qwen35", ["linux", "shell", "cli"],
              ["b-mc2/cli-commands-explained", "NickIBrody/linux-shell-corpus-ru-en",
               "rajivmehtapy/shell-script-specialist-dataset"], "mixed", "linux_kernel"),
    "kernel_vuln": ("Linux Kernel Vulnerability Commits", "kernel-vuln-qwen35",
                    ["linux", "kernel", "security", "vulnerability"],
                    ["quguanni/kernel-vuln-dataset", "pebblebed/kernel-vuln-dataset"],
                    "mixed", "linux_kernel"),
    "kernel_syzfix_sample": ("syzfix Kernel Crash Fixes (sample)", "kernel-syzfix-qwen35",
                             ["linux", "kernel", "syzbot", "debugging"],
                             ["xiaoguangwang/syzfix-dataset - 500 MB streamed sample "
                              "of 5.1 GB"], "mixed", "linux_kernel"),
    "kernel_vuln_full_sample": ("Linux Kernel Commit Diffs (sample)",
                                "kernel-vuln-full-qwen35",
                                ["linux", "kernel", "patch", "vulnerability"],
                                ["quguanni/kernel-vuln-dataset-full - 500 MB streamed "
                                 "sample of 1.9 GB"], "mixed", "linux_kernel"),
    "linux_kernel_commits": ("Linux Kernel Commit Reasoning", "linux-kernel-commits-qwen35",
                             ["linux", "kernel", "reasoning"],
                             ["ewedubs/linux-kernel-commits-aireason-instruct - "
                              "Apache-2.0"], "apache-2.0", "linux_kernel"),
    "linux_kernel_assembly": ("Linux Kernel Assembly Pairs", "linux-kernel-asm-qwen35",
                              ["linux", "kernel", "assembly", "reverse-engineering"],
                              ["theelderemo/linux-asm-pairs - GPL-2.0"], "gpl-2.0",
                              "linux_kernel"),
    "linux_kernel_ioctl": ("Linux ioctl Census", "linux-kernel-ioctl-qwen35",
                           ["linux", "kernel", "ioctl", "drivers"],
                           ["mjbommar/linux-ioctl-census - CC-BY-4.0"], "cc-by-4.0",
                           "linux_kernel"),
    "kernel_davinci": ("daVinci Triton Kernel Optimization (GPU only)",
                       "kernel-davinci-qwen35", ["gpu", "triton", "kernel", "agentic"],
                       ["GAIR/daVinci-kernel-sft - 500 MB streamed sample of 970 MB"],
                       "apache-2.0", "linux_kernel"),
    "mql5_repos": ("MQL5 Expert Advisor Source", "mql5-repos-qwen35",
                   ["mql5", "metatrader", "trading"],
                   ["homayoun-asghari/mql5-expert-advisors", "geraked/metatrader5",
                    "EA31337/EA31337-classes", "Pierre8r/All-MQL5-code"],
                   "mixed (per-repo; mostly MIT/GPL-3.0)", "mql5_optional"),
    "mql5_expanded": ("MQL5 Expert Advisor Source (expanded)", "mql5-expanded-qwen35",
                      ["mql5", "metatrader", "trading"],
                      ["52 additional MQL5 repositories discovered via the GitHub "
                       "search API (stars > 5, licence required); see "
                       "scrapers/github/repo_list.md"],
                      "mixed (per-repo)", "mql5_optional"),
    "mql5_benchmark": ("MQL5 Compile-Success Benchmark", "mql5-compile-benchmark",
                       ["mql5", "metatrader", "benchmark", "evaluation"],
                       ["CompilingThings/compile-benchmark"], "see source repository",
                       "mql5_optional"),
    "forex_calendar": ("Forex Economic Calendar", "forex-calendar-qwen35",
                       ["forex", "mql5", "trading", "economics"],
                       ["Ehsanrs2/Forex_Factory_Calendar - MIT"], "mit", "mql5_optional"),
    "generated_mql5": ("Generated MQL5 Q&A", "mql5-generated-qwen35",
                       ["mql5", "metatrader", "generated"],
                       ["Project-generated 14_mql5.jsonl (3,101 examples) authored for "
                        "this project"], "project-generated", "mql5_optional"),
    "python": ("Python Code Corpus", "python-qwen35", ["python", "code"],
               ["NickIBrody/python-code-instructions-85k",
                "ronantakizawa/python-code-instructions-japanese",
                "flytech/llama-python-codes-30k", "pythonist/PubMedQA",
                "meeAtif/python-qa-stackoverflow",
                "mrbesher/python-code-instructions-18k-alpaca-tr"], "mixed", "code_python"),
    "cpp": ("C / C++ Code Corpus", "cpp-qwen35", ["cpp", "c", "code"],
            ["shareAI/CodeChat", "Mxode/StackOverflow-QA-C-Language-40k",
             "dumb-dev/cpp-10k", "AmareshHebbar/leetcode-codegen-cpp"], "mixed",
            "code_cpp"),
    "code_review": ("Code Review Corpus", "code-review-qwen35",
                    ["code-review", "pull-request", "code"],
                    ["ronantakizawa/github-codereview - Other",
                     "code-review-bench/code-review-bench - CC-BY-4.0"],
                    "mixed (other / cc-by-4.0)", "debug_review"),
    "coding_debug": ("Coding and Debugging Traces", "debug-qwen35",
                     ["debugging", "coding", "agent"],
                     ["greghavens/kimi-k3-coding-and-debugging-traces",
                      "JetBrains-Research/agent-trajectories-swe-bench-test-minus-verified",
                      "and 27 more datasets from the curated list"], "mixed",
                     "debug_review"),
    "python_codeparrot_sample": ("CodeParrot Clean Python (sample)",
                                 "python-codeparrot-qwen35",
                                 ["python", "code", "pretraining"],
                                 ["codeparrot/codeparrot-clean - 500 MB streamed sample "
                                  "of 12.8 GB; the per-file licence field is preserved in "
                                  "the text"], "per-file (mostly MIT/Apache-2.0)",
                                 "code_python"),
    "security_data": ("Security and AppSec Corpus", "security-qwen35",
                      ["security", "appsec", "cve"],
                      ["Trendyol/Trendyol-Cybersecurity-Instruction-Tuning-Dataset",
                       "AlicanKiraz0/Cybersecurity-Dataset-Heimdall-v1.1",
                       "mlfoundations-dev/stackexchange_security and 11 more"], "mixed",
                      "security"),
    "security_qa": ("NVD and OWASP Question Answering", "security-qa-qwen35",
                    ["security", "cve", "owasp", "qa"],
                    ["shahrukh95/OWASP-and-NVD-question-answer-dataset",
                     "shahrukh95/NVD-question-answer-dataset"], "see source datasets",
                    "security"),
    "security_expanded": ("Secure Coding and Vulnerability Fixes",
                          "security-expanded-qwen35",
                          ["security", "secure-coding", "vulnerability"],
                          ["ayshajavd/code-security-vulnerability-dataset - Apache-2.0",
                           "lemon42-ai/Code_Vulnerability_Labeled_Dataset - Apache-2.0",
                           "jondurbin/bagel-llama-3-v1.0 - Apache-2.0 (500 MB sample)"],
                          "apache-2.0 (mixed)", "security"),
    "agent_tool": ("Agentic Tool-Use Corpus", "agent-tool-qwen35",
                   ["agents", "tool-use", "function-calling"],
                   ["NousResearch/hermes-function-calling-v1",
                    "allenai/Dolci-Instruct-SFT-Tool-Use-SA",
                    "Mustafaege/qwen3.5-toolcalling-v1 and 45 more"], "mixed", "agent_tool"),
    "reasoning_algorithms": ("Reasoning and Algorithms", "reasoning-qwen35",
                             ["reasoning", "algorithms", "chain-of-thought"],
                             ["0x22almostEvil/reasoning-gsm-qna-oa",
                              "HuggingFaceTB/CoT_Reasoning_Bushcraft_Survival",
                              "Conversational-Reasoning/Topical-Chat and 25 more"],
                             "mixed", "reasoning"),
    "uncategorized": ("Uncategorised Grab Bag", "uncategorized-qwen35",
                      ["mixed", "misc"],
                      ["seablue/DiDi_GAIA_dataset_jsonl",
                       "Chinese-Vicuna/instruct_chat_50k.jsonl",
                       "ostapeno/qa-platy-* (4 datasets that matched no expert "
                       "category)"], "mixed", "unassigned"),
}

CAVEATS = {
    "kernel_davinci": """
## Training Requirements

GPU required. This corpus contains agentic Triton coding sessions that average
more than 8192 tokens. The tokenize-and-drop check showed 100% truncation at
`max_length=8192`. Training requires a GPU with context length greater than
8192 (A100, RTX 4090, H100). It is not trainable on the local CPU pipeline.
""",
    "mql5_benchmark": """
## Important: Evaluation Set, Not Training Data

**This is a compile-success evaluation set, not a training corpus.** The
original release (`CompilingThings/compile-benchmark`) ships prompts and
compile verdicts but withholds the actual code completions (marked
`private_outputs` in its `PROJECTION_REPORT.json`). The assistant turn in each
record is the release's verdict label, not MQL5 code. Use this dataset to
evaluate whether a model produces compilable MQL5, not to train one.
""",
    "uncategorized": """
## Note on Scope

This is a heterogeneous grab bag from the initial dataset download. It is not
assigned to a specific expert. Suitable for router training, general-purpose
mixing, or as a source pool for future expert-specific filtering.
""",
}

DESCRIPTIONS = {
    "android": "Teaches Android application and LineageOS custom-ROM work: "
               "Kotlin/Compose UI, AndroidControl device actions and support answers.",
    "lineageos_tree": "Teaches how the Android/LineageOS platform is built: framework "
                      "Java/Kotlin, Soong (Android.bp) and Make build files, device "
                      "trees for the Galaxy A04s, Exynos850 kernel drivers and SELinux "
                      "policy.",
    "kernel_davinci": "Teaches agentic GPU-kernel optimisation: rewriting PyTorch "
                      "modules as Triton kernels over multiple rounds with measured "
                      "speedups.",
    "mql5_benchmark": "An evaluation set of MQL5 coding prompts with the release's "
                      "compile verdict for each.",
    "uncategorized": "A mixed pool of instruction data that did not match any single "
                     "expert category.",
}


def card_markdown(category, meta, n_train, n_val, prefix) -> str:
    name, repo, tags, sources, license_id, expert = meta
    description = DESCRIPTIONS.get(
        category, "Teaches domain-specific instruction following and code generation "
                  "for this expert.")
    source_lines = "\n".join(f"- {s}" for s in sources)
    tag_lines = "\n".join(f"  - {t}" for t in tags + ["qwen3.5", "conversation",
                                                     "instruction-tuning"])
    total = n_train + n_val
    size_cat = "1M+" if total >= 1_000_000 else ("100K" if total >= 100_000 else "10K")
    caveat = CAVEATS.get(category, "")
    return f"""---
language:
  - en
license: {frontmatter_license(license_id)}
task_categories:
  - text-generation
tags:
{tag_lines}
size_categories:
  - {size_cat}
---

# {name}

## Description

{description}
{caveat}
## Source

{source_lines}

Formatted for the MoE-orchestrator project
(https://github.com/michaelowusuntim6/MoE-orchestrator). Expert target:
`{expert}`.

## Format

Each record is a JSON object with a `messages` field formatted for Qwen3.5's
native chat template:

```json
{{"messages": [
  {{"role": "system", "content": "..."}},
  {{"role": "user", "content": "..."}},
  {{"role": "assistant", "content": "..."}}
]}}
```

The records are consumed via `tokenizer.apply_chat_template()`. Special tokens
(`<|im_start|>`, `<|im_end|>`) are added by the template, never embedded in
content.

## Splits

- `train`: {n_train:,} records
- `val`: {n_val:,} records

## Usage

```python
from datasets import load_dataset
ds = load_dataset("{prefix}/{repo}", split="train")
print(ds[0]["messages"])
```

## License

{license_id}. Upstream sources keep their own licences - see the source list
above and `docs/DATASET_SOURCES.md` in the MoE-orchestrator repository for
per-source detail.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write dataset cards")
    parser.add_argument("--config", default=None)
    parser.add_argument("--formatted-root", default=None)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    root = (Path(args.formatted_root) if args.formatted_root
            else cfg.path_for("Formatted_datasets", "formatted_root",
                              "datasets/formatted"))
    prefix = cfg.get_str("HF_Upload", "repo_prefix",
                         cfg.get_str("Upload", "hf_upload_repo_prefix",
                                     "michaelowusuntim6"))

    written = 0
    for category, meta in META.items():
        folder = root / category
        manifest = folder / "manifest.json"
        if not manifest.is_file():
            print(f"SKIP {category}: no manifest")
            continue
        data = json.loads(manifest.read_text())
        (folder / "README.md").write_text(
            card_markdown(category, meta, data.get("train_lines", 0),
                          data.get("val_lines", 0), prefix), encoding="utf-8")
        written += 1
    print(f"cards written: {written}/{len(META)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
