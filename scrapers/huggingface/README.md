# Hugging Face scrapers

## `hf_search.py`

Searches the Hub for datasets matching every keyword in
`hf_search_keywords`, keeps results with at least `hf_search_min_downloads`,
then fetches size and gated status and marks each result downloadable or
skipped.

```
--dry-run             print the searches (no API calls)
--keyword KW          restrict to one keyword (repeatable)
--limit N             override hf_search_max_results
--min-downloads N     override hf_search_min_downloads
--max-size-lookups N  cap dataset_info calls used to fetch sizes
--download            download everything that passes the guards
--category NAME       category folder for --download
--output PATH         override scrapers/logs/hf_search_results.json
```

Output: `scrapers/logs/hf_search_results.json` — per keyword `{hits, kept}`
plus one record per dataset (`id, downloads, likes, tags, gated, size_bytes,
max_file_bytes, skip_reasons, downloadable`).

## `hf_downloader.py`

Downloads the curated list in `dataset_list.md` (`## category` headers, one
dataset id per line, optional `category: name`).

```
--dry-run             list decisions; no API calls, no downloads
--category NAME       restrict to one category (repeatable)
--dataset ID          restrict to one dataset (repeatable)
--limit N             cap the number of datasets
--force               re-download even if the directory has files
--allow-large         ignore the file/dataset size ceilings
```

Per dataset: query size/gated → skip if gated (`hf_skip_gated`), over
`hf_max_dataset_mb`, or any file over `hf_max_file_mb` → otherwise
`snapshot_download` into
`datasets/public/huggingface/<category>/<owner>__<name>/`. Retries use
`download_retry_attempts` / `download_retry_backoff_seconds`; each attempt
is a subprocess with `download_timeout_seconds` and a 500 MB-per-file guard.

Outputs: `scrapers/logs/download.log` and `scrapers/logs/status.json`.

## `hf_uploader.py`

Publishes a formatted corpus as a dataset repo. Reads `## Upload`
(`hf_upload_repo_prefix`, `hf_upload_private`,
`hf_upload_commit_message_prefix`, `hf_upload_readme_template`) and renders
`README.template.md` into the folder before uploading.

```
--name NAME        dataset name (repo suffix)
--path PATH        local folder to upload
--dry-run          render the card and print the plan; no upload
--private          create the repo private
--description/--source/--license/--category   card fields
--repo-id ID       override <prefix>/<name>
```

The token comes from `HF_TOKEN`; the script refuses to upload without it.
