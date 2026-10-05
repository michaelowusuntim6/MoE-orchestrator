#!/usr/bin/env python3
"""Upload a formatted corpus to the Hugging Face Hub as a dataset repo.

Reads `## Upload` from config.md (repo prefix, private flag, commit-message
prefix, README template). The token always comes from the environment
(`HF_TOKEN` by default) and is never written anywhere.

    ./venv-inference/bin/python scrapers/huggingface/hf_uploader.py \
        --name code-python --path datasets/formatted/python --dry-run
    ./venv-inference/bin/python scrapers/huggingface/hf_uploader.py \
        --name code-python --path datasets/formatted/python
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.common import human_bytes, load_config  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="hf_uploader.py",
        description="Upload a formatted corpus as an HF dataset.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--name", required=True, help="Dataset name (repo suffix)")
    parser.add_argument("--path", required=True, help="Local folder to upload")
    parser.add_argument("--dry-run", action="store_true",
                        help="Render the card and print the plan; no upload")
    parser.add_argument("--private", action="store_true",
                        help="Create the repo as private")
    parser.add_argument("--description", default=None, help="Card description")
    parser.add_argument("--source", default=None, help="Source attribution line")
    parser.add_argument("--license", default="apache-2.0", help="License id")
    parser.add_argument("--category", default=None, help="Card tag/category")
    parser.add_argument("--repo-id", default=None,
                        help="Override <prefix>/<name> entirely")
    return parser.parse_args(argv)


def count_records(folder: Path) -> int:
    total = 0
    for name in ("train.jsonl", "val.jsonl"):
        path = folder / name
        if path.is_file():
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                total += sum(1 for line in handle if line.strip())
    return total


def render_card(cfg, folder: Path, repo_id: str, name: str, args) -> str:
    template_path = cfg.path_for("Upload", "hf_upload_readme_template",
                                 "scrapers/huggingface/README.template.md")
    template = template_path.read_text(encoding="utf-8")
    manifest = folder / "manifest.json"
    formatter_version = "unknown"
    if manifest.is_file():
        try:
            formatter_version = json.loads(manifest.read_text())["formatter_version"]
        except Exception:
            pass
    fields = {
        "name": name,
        "repo_id": repo_id,
        "description": args.description or f"{name} corpus for Qwen3.5 LoRA experts.",
        "source": args.source or "See docs/DATASET_SOURCES.md in the MoE-orchestrator repo.",
        "license": args.license,
        "category": args.category or name,
        "records": f"{count_records(folder):,}",
        "formatter_version": formatter_version,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    card = template
    for key, value in fields.items():
        card = card.replace("{" + key + "}", str(value))
    return card


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    upload = "Upload"

    folder = Path(args.path).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"error: upload path is not a directory: {folder}")
    prefix = cfg.get_str(upload, "hf_upload_repo_prefix", "")
    repo_id = args.repo_id or (f"{prefix}/{args.name}" if prefix else args.name)
    private = args.private or cfg.get_bool(upload, "hf_upload_private", False)
    token_env = cfg.get_str("Scrapers", "hf_token_env", "HF_TOKEN")
    token = os.environ.get(token_env) or None
    commit_prefix = cfg.get_str(upload, "hf_upload_commit_message_prefix", "v1")

    files = sorted(p for p in folder.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in files)
    card = render_card(cfg, folder, repo_id, args.name, args)

    print(f"repo_id      : {repo_id}  (private={private})")
    print(f"folder       : {folder}")
    print(f"files        : {len(files)}  ({human_bytes(size)})")
    print(f"records      : {count_records(folder):,}")
    print(f"token        : {'set' if token else 'NOT SET (%s)' % token_env}")
    print(f"commit msg   : {commit_prefix}: upload {args.name}")
    print(f"README.md    : {len(card)} chars rendered from the template")

    if args.dry_run:
        print("\n--dry-run: would write README.md to the folder and call\n"
              f"  HfApi.create_repo('{repo_id}', repo_type='dataset', private={private}, exist_ok=True)\n"
              f"  HfApi.upload_folder('{repo_id}', folder_path='{folder}', repo_type='dataset')\n"
              f"  -> https://huggingface.co/datasets/{repo_id}")
        print("\n--- rendered README.md (first 20 lines) ---")
        print("\n".join(card.splitlines()[:20]))
        return 0

    if not token:
        raise SystemExit(f"error: {token_env} is not set; refusing to upload")

    try:
        from huggingface_hub import HfApi
        api = HfApi(token=token)
        api.create_repo(repo_id=repo_id, repo_type="dataset", private=private,
                        exist_ok=True)
        (folder / "README.md").write_text(card, encoding="utf-8")
        api.upload_folder(repo_id=repo_id, folder_path=str(folder),
                          repo_type="dataset",
                          commit_message=f"{commit_prefix}: upload {args.name}")
    except Exception as exc:
        print(f"error: upload failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"\nuploaded -> {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
