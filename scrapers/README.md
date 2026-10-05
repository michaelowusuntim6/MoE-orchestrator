# Scrapers — dataset acquisition infrastructure

Everything here reads **one** config file: `../config.md` (via
`orchestrator.config.Config` and the shared helpers in `common.py`). There
are no secondary config files.

| tool | purpose | output |
|---|---|---|
| `huggingface/hf_search.py` | search HF for datasets in our fields | `logs/hf_search_results.json` |
| `huggingface/hf_downloader.py` | download the curated dataset list | `datasets/public/huggingface/<category>/` |
| `huggingface/hf_uploader.py` | publish a formatted corpus | HF dataset repo |
| `github/github_scraper.py` | clone the curated repo list | `datasets/public/github/<category>/` |
| `lineageos/lineageos_walker.py` | catalog the local LineageOS tree | `datasets/public/lineageos_tree/_catalog.json` |
| `lineageos/aosp_scraper.py` | emit AOSP snippet records | `datasets/public/lineageos_tree/aosp_snippets.jsonl` |

## Size limits (the hard rule)

**No single downloaded file may exceed 500 MB.** It is enforced in two
places, both driven by config:

* `scrapers/common.py::over_file_limit(size, limit_mb, allow_large)` — the
  single predicate every scraper calls.
* Per-tool ceilings: `hf_max_file_mb` / `hf_max_dataset_mb`,
  `github_max_file_mb` / `github_max_repo_mb`, `lineageos_max_file_mb`.

`--allow-large` (HF + GitHub) overrides the ceilings for a conscious run.
The LineageOS walker never overrides: oversized files are simply skipped and
counted.

## Running everything safely

All five tools support `--dry-run`, which prints the plan without calling an
API (except the LineageOS walker, which reads the local tree) and without
downloading anything:

```bash
cd ~/MoE-orchestrator
./venv-inference/bin/python scrapers/huggingface/hf_search.py --dry-run
./venv-inference/bin/python scrapers/huggingface/hf_downloader.py --dry-run
./venv-inference/bin/python scrapers/github/github_scraper.py --dry-run
./venv-inference/bin/python scrapers/lineageos/lineageos_walker.py --dry-run
```

Logs: `logs/download.log`. Status: `logs/status.json` (rewritten by each
download run). Tokens come from the environment (`HF_TOKEN`, `GITHUB_TOKEN`)
and are never written to disk.
