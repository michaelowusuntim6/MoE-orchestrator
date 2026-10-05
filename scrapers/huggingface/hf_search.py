#!/usr/bin/env python3
"""Search the Hugging Face Hub for datasets in the MoE fields of interest.

Reads every tunable from config.md (`## Scrapers`). The search itself makes
API calls; `--dry-run` makes none. Nothing is downloaded unless `--download`
is passed, and then only datasets that pass the 500 MB per-file and
dataset-size guards.

    ./venv-inference/bin/python scrapers/huggingface/hf_search.py --dry-run
    ./venv-inference/bin/python scrapers/huggingface/hf_search.py
    ./venv-inference/bin/python scrapers/huggingface/hf_search.py --download --category android
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import MB, human_bytes, load_config, now_iso, over_file_limit  # noqa: E402

DEFAULT_RESULTS = PROJECT_ROOT / "scrapers" / "logs" / "hf_search_results.json"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="hf_search.py",
        description="Search HF datasets for the configured keywords.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None, help="Path to config.md")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the searches that would run; no API calls")
    parser.add_argument("--keyword", action="append", default=None,
                        help="Restrict to one keyword (repeatable)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Override hf_search_max_results")
    parser.add_argument("--min-downloads", type=int, default=None,
                        help="Override hf_search_min_downloads")
    parser.add_argument("--max-size-lookups", type=int, default=400,
                        help="Cap on dataset_info calls used to fetch sizes")
    parser.add_argument("--download", action="store_true",
                        help="Download the datasets that pass the guards")
    parser.add_argument("--category", default="hf_search",
                        help="Category directory for --download results")
    parser.add_argument("--output", default=None, help="Override results JSON path")
    return parser.parse_args(argv)


def size_and_gated(api, repo_id: str, token):
    """(total_bytes, gated, largest_file_bytes, error) for one dataset."""
    try:
        info = api.dataset_info(repo_id, files_metadata=True, token=token)
    except Exception as exc:
        return None, None, None, f"{type(exc).__name__}: {exc}"
    sizes = [getattr(s, "size", None) for s in (info.siblings or [])]
    sizes = [s for s in sizes if isinstance(s, int)]
    return (sum(sizes) if sizes else None,
            bool(getattr(info, "gated", False)),
            (max(sizes) if sizes else None),
            None)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    scrapers = "Scrapers"

    keywords = args.keyword or cfg.get_list(scrapers, "hf_search_keywords")
    limit = args.limit or cfg.get_int(scrapers, "hf_search_max_results", 100)
    min_downloads = (args.min_downloads if args.min_downloads is not None
                     else cfg.get_int(scrapers, "hf_search_min_downloads", 10))
    workers = cfg.get_int(scrapers, "download_workers", 2) or 1
    max_file_mb = cfg.get_int(scrapers, "hf_max_file_mb", 500)
    max_dataset_mb = cfg.get_int(scrapers, "hf_max_dataset_mb", 5120)
    skip_gated = cfg.get_bool(scrapers, "hf_skip_gated", True)
    token = os.environ.get(cfg.get_str(scrapers, "hf_token_env", "HF_TOKEN")) or None
    results_path = Path(args.output) if args.output else DEFAULT_RESULTS

    print(f"keywords        : {', '.join(keywords)}")
    print(f"results/keyword : {limit}")
    print(f"min downloads   : {min_downloads}")
    print(f"size guards     : file <= {max_file_mb} MB, dataset <= {max_dataset_mb} MB")
    print(f"token           : {'set' if token else 'not set (public search only)'}")

    if args.dry_run:
        print("\n--dry-run: would call, per keyword:")
        for kw in keywords:
            print(f"  list_datasets(search={kw!r}, limit={limit}, "
                  f"sort='downloads', direction=-1)")
        print(f"\nwould filter downloads < {min_downloads}, then fetch sizes and "
              f"drop gated={skip_gated} / oversize datasets")
        print(f"would write results to {results_path}")
        return 0

    from huggingface_hub import HfApi
    api = HfApi()

    per_keyword, candidates = {}, {}
    for kw in keywords:
        try:
            found = list(api.list_datasets(search=kw, limit=limit, token=token,
                                           sort="downloads", direction=-1))
        except Exception as exc:
            per_keyword[kw] = {"hits": 0, "kept": 0, "error": f"{type(exc).__name__}: {exc}"}
            print(f"  {kw:18} ERROR {type(exc).__name__}: {exc}")
            continue
        kept = 0
        for ds in found:
            downloads = getattr(ds, "downloads", 0) or 0
            if downloads < min_downloads:
                continue
            kept += 1
            entry = candidates.setdefault(ds.id, {
                "id": ds.id,
                "downloads": downloads,
                "likes": getattr(ds, "likes", 0),
                "tags": list(getattr(ds, "tags", []) or []),
                "gated": bool(getattr(ds, "gated", False)),
                "keywords": [],
            })
            entry["downloads"] = max(entry["downloads"], downloads)
            entry["keywords"].append(kw)
        per_keyword[kw] = {"hits": len(found), "kept": kept}
        print(f"  {kw:18} {kept:4} kept (of {len(found)} hits)")

    ordered = sorted(candidates.values(), key=lambda e: -e["downloads"])
    to_enrich = ordered[: max(0, args.max_size_lookups)]
    print(f"\nfetching size/gated metadata for {len(to_enrich)} datasets "
          f"({workers} workers) ...")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        enriched = list(pool.map(
            lambda e: (e, *size_and_gated(api, e["id"], token)), to_enrich))
    for entry, total, gated, biggest, err in enriched:
        entry["size_bytes"] = total
        entry["max_file_bytes"] = biggest
        if gated is not None:
            entry["gated"] = gated
        if err:
            entry["error"] = err
        reasons = []
        if entry.get("gated") and skip_gated:
            reasons.append("gated")
        if total is not None and total > max_dataset_mb * MB:
            reasons.append(f"dataset_too_large ({human_bytes(total)})")
        if over_file_limit(biggest, max_file_mb):
            reasons.append(f"file_too_large ({human_bytes(biggest)})")
        entry["skip_reasons"] = reasons
        entry["downloadable"] = not reasons

    payload = {"generated_at": now_iso(), "keywords": keywords,
               "min_downloads": min_downloads, "per_keyword": per_keyword,
               "size_lookups": len(to_enrich), "datasets": ordered}
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    downloadable = [d for d in ordered if d.get("downloadable")]
    print(f"\ndatasets kept : {len(ordered)}")
    print(f"downloadable  : {len(downloadable)}")
    print(f"results       : {results_path}")

    if args.download and downloadable:
        from scrapers.huggingface.hf_downloader import download_dataset, open_log
        log = open_log(cfg)
        try:
            for entry in downloadable:
                download_dataset(cfg, entry["id"], args.category, log,
                                 force=False, dry_run=False)
        finally:
            log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
