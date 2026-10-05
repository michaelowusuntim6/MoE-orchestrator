# GitHub scraper

Clones the repositories in `repo_list.md` into
`datasets/public/github/<category>/<owner>__<name>/`.

## Config keys (`## Scrapers` in config.md)

`github_token_env`, `github_max_file_mb`, `github_max_repo_mb`,
`github_clone_depth`, `github_skip_forks`, `github_skip_archived`,
`github_timeout_seconds`, `github_repos_file`, `github_output_root`,
`download_log_file`, `download_status_file`.

## CLI

```
--config PATH     alternative config.md
--dry-run         list what would be cloned (no API calls, no clones)
--category NAME   restrict to one category (repeatable)
--repo OWNER/NAME restrict to one repo (repeatable)
--limit N         cap the number of repos
--force           re-clone even if the directory already has files
--allow-large     ignore the repo/file size ceilings
```

## Behavior

1. `GET https://api.github.com/repos/<id>` → size, default_branch, archived, fork.
2. Skip forks (`github_skip_forks`), archived repos (`github_skip_archived`),
   and repos over `github_max_repo_mb` (unless `--allow-large`).
3. `git clone --depth <github_clone_depth>`.
4. Walk the clone and **delete** files over `github_max_file_mb`, recording
   each in `_truncated.json` inside the cloned repo directory.
5. Resumable: a directory that already contains files is skipped.

## Size-limit behavior

Repo size is checked before cloning; file size is enforced after cloning by
deletion (with a record), so a repo with one huge blob still yields a usable
checkout. `GITHUB_TOKEN` raises the API rate limit from 60 to 5000 req/h.
