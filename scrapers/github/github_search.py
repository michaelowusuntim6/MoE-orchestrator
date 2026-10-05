#!/usr/bin/env python3
"""Search GitHub for MQL5 / Android repositories, gated before cloning.

Search results already carry stars, license, size, fork and archived flags,
so the whole quality gate runs from one request per query — no wasted API
budget on repos that will be rejected anyway.

Kernel repositories stay excluded by project policy (see repo_list.md), so
kernel-flavoured hits are reported but never appended to the clone list.

    ./venv-inference/bin/python scrapers/github/github_search.py --dry-run
    ./venv-inference/bin/python scrapers/github/github_search.py --append
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import load_config  # noqa: E402

SEARCH_API = "https://api.github.com/search/repositories"
DEFAULT_QUERIES = [
    "topic:mql5 language:MQL5 stars:>5",
    "topic:expert-advisor language:MQL5",
    "topic:forex-robot language:MQL5",
    "topic:metatrader5 language:MQL5",
    "topic:algorithmic-trading language:MQL5",
    "topic:android-kernel language:C stars:>10",
    "topic:lineageos language:Makefile stars:>5",
    "topic:android-rom language:Shell stars:>5",
]

# Project policy: kernel trees are not cloned (the local LineageOS tree covers
# kernel source), and android_kernel was removed from repo_list.md.
POLICY_EXCLUDED_TOPIC_MARKERS = ("android-kernel", "lineageos", "android-rom")

RESULTS_PATH = PROJECT_ROOT / "scrapers" / "logs" / "github_search_results.json"
REPO_LIST = PROJECT_ROOT / "scrapers" / "github" / "repo_list.md"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="github_search.py",
        description="Search GitHub for MQL5/Android repos and gate them.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="List the queries; no API calls")
    parser.add_argument("--query", action="append", default=None,
                        help="Extra/alternative search query (repeatable)")
    parser.add_argument("--min-stars", type=int, default=None)
    parser.add_argument("--limit", type=int, default=30, help="Results per query")
    parser.add_argument("--output", default=None)
    parser.add_argument("--append", action="store_true",
                        help="Append passing MQL5 repos to repo_list.md")
    parser.add_argument("--category", default="mql5")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    scrapers = "Scrapers"
    queries = args.query or DEFAULT_QUERIES
    min_stars = args.min_stars if args.min_stars is not None else cfg.get_int(
        scrapers, "quality_gate_min_stars", 5)
    require_license = cfg.get_bool(scrapers, "quality_gate_require_license", True)
    gate_enabled = cfg.get_bool(scrapers, "quality_gate_enabled", True)
    max_repo_mb = cfg.get_int(scrapers, "github_max_repo_mb", 2048)
    token = os.environ.get(cfg.get_str(scrapers, "github_token_env", "GITHUB_TOKEN")) or None
    out_path = Path(args.output) if args.output else RESULTS_PATH

    print(f"queries      : {len(queries)}")
    print(f"min stars    : {min_stars}   require license: {require_license}")
    print(f"token        : {'set' if token else 'not set (search limited to 10 req/min)'}")
    print(f"policy       : kernel/lineageos/ROM repos are reported but never cloned")

    if args.dry_run:
        print("\n--dry-run: would call search/repositories for:")
        for q in queries:
            print(f"  {q}")
        print(f"\nwould write {out_path}")
        return 0

    import requests
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    per_query, found = {}, {}
    for query in queries:
        try:
            response = requests.get(SEARCH_API,
                                    params={"q": query, "sort": "stars",
                                            "order": "desc", "per_page": args.limit},
                                    headers=headers, timeout=30)
        except Exception as exc:
            per_query[query] = {"error": f"{type(exc).__name__}: {exc}", "hits": 0}
            print(f"  {query[:52]:54} ERROR")
            continue
        if response.status_code != 200:
            per_query[query] = {"error": f"HTTP {response.status_code}", "hits": 0}
            print(f"  {query[:52]:54} HTTP {response.status_code}")
            time.sleep(2)
            continue
        items = response.json().get("items", [])
        kept = 0
        for repo in items:
            full = repo.get("full_name")
            if not full:
                continue
            lic = (repo.get("license") or {}).get("spdx_id")
            size_mb = (repo.get("size") or 0) / 1024
            reasons = []
            if gate_enabled:
                if (repo.get("stargazers_count") or 0) < min_stars:
                    reasons.append(f"low_stars({repo.get('stargazers_count')})")
                if require_license and not lic:
                    reasons.append("no_license")
                if repo.get("archived"):
                    reasons.append("archived")
                if repo.get("fork"):
                    reasons.append("fork")
                if not (repo.get("description") or "").strip():
                    reasons.append("no_description")
            if size_mb > max_repo_mb:
                reasons.append(f"repo_too_large({size_mb:.0f}MB)")
            if any(marker in query for marker in POLICY_EXCLUDED_TOPIC_MARKERS):
                reasons.append("policy_kernel_or_rom_excluded")
            entry = found.setdefault(full, {
                "repo": full, "stars": repo.get("stargazers_count"),
                "license": lic, "size_mb": round(size_mb, 2),
                "archived": repo.get("archived"), "fork": repo.get("fork"),
                "description": (repo.get("description") or "")[:200],
                "queries": [], "reasons": [],
            })
            entry["queries"].append(query)
            entry["reasons"] = sorted(set(entry["reasons"]) | set(reasons))
            if not reasons:
                kept += 1
        per_query[query] = {"hits": len(items), "passing": kept}
        print(f"  {query[:52]:54} {kept:3} passing / {len(items)} hits")
        time.sleep(2)  # stay under the unauthenticated search limit

    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "queries": queries, "per_query": per_query,
        "min_stars": min_stars,
        "repos": sorted(found.values(), key=lambda r: -(r.get("stars") or 0)),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    passing = [r for r in payload["repos"] if not r["reasons"]]
    print(f"\nunique repos  : {len(payload['repos'])}")
    print(f"passing gate  : {len(passing)}")
    for repo in passing:
        print(f"  {repo['stars']:>5}*  {repo['repo']:52} {repo['size_mb']:>7} MB  "
              f"{repo['license']}")
    print(f"results       : {out_path}")

    if args.append and passing:
        existing = REPO_LIST.read_text(encoding="utf-8")
        lines = [existing.rstrip(), "", f"# Discovered by github_search.py on 2026-10-05",
                 f"## {args.category}"]
        added = 0
        for repo in passing:
            if repo["repo"] in existing:
                continue
            lines.append(f"# {repo['stars']}* · {repo['size_mb']} MB · {repo['license']}")
            lines.append(repo["repo"])
            added += 1
        if added:
            REPO_LIST.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"appended      : {added} repos -> {REPO_LIST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
