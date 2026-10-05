# LineageOS tree scrapers

Both tools treat `/run/media/mike/Android/lineage-23.2/` as **read only** —
they never create, modify, or delete anything inside the tree. Output goes to
`lineageos_output_root` (`datasets/public/lineageos_tree/`).

## `lineageos_walker.py`

Walks the tree and catalogs source files.

```
--dry-run          count matching files without hashing
--sample N         hash only the first N files (fast preview)
--root PATH        override lineageos_tree_root
--output PATH      override the catalog path
--max-files N      override lineageos_max_files
```

Config keys: `lineageos_tree_root`, `lineageos_max_file_mb`,
`lineageos_include_extensions`, `lineageos_skip_dirs`,
`lineageos_max_files`.

Ordering: device-specific areas first
(`device/samsung/a04s`, `kernel/samsung/exynos850`, `vendor/samsung/a04s`,
then the rest of `device/samsung`, `vendor/samsung`, `kernel/samsung`) so a
truncated catalog still contains the most relevant code for the A04s.

Output: `_catalog.json` with `{path, size, ext, priority, sha256}` per file
plus totals, extension counts, and how many oversized files were skipped
(`lineageos_max_file_mb`).

## `aosp_scraper.py`

Emits Qwen3.5 chat records whose assistant turn is a real AOSP-derived source
file from the local tree (LineageOS is an AOSP fork, so no network fetch is
needed).

```
--path PATH        tree-relative path to scan (repeatable)
--dry-run          report candidates; write nothing
--limit N          max snippet records to emit
--output PATH      override output JSONL path
--allow-remote     reserved for a future android.googlesource.com fetch
```

Default scan paths: `frameworks/base/core/java/android`,
`frameworks/base/services/core/java/com/android/server`, `system/core`,
`libcore`, `packages/modules`.

Output: `aosp_snippets.jsonl` (canonical `{"messages": [...]}` records, so
the formatter can consume them directly).
