"""
Real Hugging Face model registry & local weight downloader.
Usage:
    python -m models.registry list
    python -m models.registry download qwen2.5-7b-instruct
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any

STACK_ROOT = Path(__file__).resolve().parent.parent
if str(STACK_ROOT) not in sys.path:
    sys.path.insert(0, str(STACK_ROOT))

from config.settings import load_models_config, settings


def get_all_models() -> Dict[str, Dict[str, Any]]:
    cfg = load_models_config()
    combined: Dict[str, Dict[str, Any]] = {}
    for key, val in cfg.get("chat_models", {}).items():
        combined[key] = {**val, "kind": "chat"}
    for key, val in cfg.get("embedding_models", {}).items():
        combined[key] = {**val, "kind": "embedding"}
    return combined


def download_model(model_key: str, target_dir: Path | None = None) -> Path:
    """Download real model weights from Hugging Face Hub into models/weights/<model_key>."""
    from huggingface_hub import snapshot_download

    all_models = get_all_models()
    if model_key not in all_models:
        raise ValueError(f"Unknown model '{model_key}'. Available: {', '.join(all_models.keys())}")

    spec = all_models[model_key]
    hf_repo = spec["hf_repo"]
    if spec.get("gated") and not (settings.HF_TOKEN or os.getenv("HF_TOKEN")):
        raise RuntimeError(
            f"Model '{hf_repo}' is gated on Hugging Face. Export HF_TOKEN with your access token first."
        )

    dest = (target_dir or settings.MODELS_CACHE_DIR) / model_key
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {hf_repo} -> {dest} ...")
    local_path = snapshot_download(
        repo_id=hf_repo,
        local_dir=str(dest),
        token=settings.HF_TOKEN or os.getenv("HF_TOKEN") or None,
    )
    print(f"Download complete: {local_path}")
    return Path(local_path)


def main():
    parser = argparse.ArgumentParser(description="Manage self-hosted LLM weights")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List configured open-weight models")
    dl = sub.add_parser("download", help="Download model weights from Hugging Face")
    dl.add_argument("model_key", help="Model key from config/models.yaml")

    args = parser.parse_args()
    if args.command == "list":
        for key, spec in get_all_models().items():
            print(f"- {key} [{spec['kind']}] -> {spec['hf_repo']} (gated={spec.get('gated', False)})")
    elif args.command == "download":
        download_model(args.model_key)


if __name__ == "__main__":
    main()
