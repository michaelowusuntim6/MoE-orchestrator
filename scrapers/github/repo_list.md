# GitHub Repos to Scrape

Verified against the GitHub API on 2026-10-05 (unauthenticated; set
GITHUB_TOKEN for a higher rate limit). Sizes are the API's `size` field
(KiB).

Guards from config.md `## Scrapers`: repos are skipped when they are forks
(`github_skip_forks: true`), archived (`github_skip_archived: false`, so
archived repos are kept), or larger than `github_max_repo_mb` (2048).
Individual files over `github_max_file_mb` (500) are deleted after cloning
and recorded in `_truncated.json`.

## mql5
# homayoun-asghari/mql5-expert-advisors — 0.1 MB — DOWNLOADABLE
homayoun-asghari/mql5-expert-advisors
# geraked/metatrader5 — 10.2 MB — DOWNLOADABLE
geraked/metatrader5
# EA31337/EA31337-classes — 9.5 MB — DOWNLOADABLE
EA31337/EA31337-classes
# Pierre8r/All-MQL5-code — 2.1 MB — DOWNLOADABLE
Pierre8r/All-MQL5-code

## android_kernel
# LineageOS/android_kernel_samsung_exynos850 — 2201 MB — SKIP at the default
# 2048 MB cap; pass --allow-large (or raise github_max_repo_mb) to clone it.
LineageOS/android_kernel_samsung_exynos850
# samsungexynos850/local_manifests — 0.0 MB — DOWNLOADABLE
samsungexynos850/local_manifests
# lesdieuxx/android_kernel_a047f_resukisu — 218 MB — DOWNLOADABLE
lesdieuxx/android_kernel_a047f_resukisu
