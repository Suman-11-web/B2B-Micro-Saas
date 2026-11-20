"""
Centralized configuration loader for the self-hosted LLM stack.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

STACK_ROOT = Path(__file__).resolve().parent.parent
MODELS_CONFIG_PATH = STACK_ROOT / "config" / "models.yaml"


def load_models_config() -> Dict[str, Any]:
    """Load model definitions from config/models.yaml."""
    if not MODELS_CONFIG_PATH.exists():
        return {"chat_models": {}, "embedding_models": {}}
    with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class StackSettings:
    """Environment-backed runtime settings for Gateway, Engine, and RAG."""

    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    LLM_GATEWAY_API_KEY: str = os.getenv("LLM_GATEWAY_API_KEY", "")
    LLM_GATEWAY_PORT: int = int(os.getenv("LLM_GATEWAY_PORT", "8100"))
    VLLM_URL: str = os.getenv("VLLM_URL", "http://localhost:8001")
    RAG_URL: str = os.getenv("RAG_URL", "http://localhost:8002")
    LLM_API_URL: str = os.getenv("LLM_API_URL", "http://localhost:8100")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://b2b:b2bpassword@localhost:5432/b2b")
    MODELS_CACHE_DIR: Path = Path(os.getenv("MODELS_CACHE_DIR", str(STACK_ROOT / "models" / "weights")))
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    RATE_LIMIT: int = int(os.getenv("RATE_LIMIT", "120"))


settings = StackSettings()
