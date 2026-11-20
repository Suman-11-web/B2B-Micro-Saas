#!/usr/bin/env python3
"""
End-to-end smoke test for the self-hosted LLM API Gateway.
Tests: /health, /v1/models, /v1/embeddings, and /v1/chat/completions.
Usage:
    LLM_GATEWAY_URL=http://localhost:8100 LLM_API_KEY=<token_or_key> python scripts/test_stack.py
"""
from __future__ import annotations

import os
import sys
import httpx


def main():
    base_url = os.getenv("LLM_GATEWAY_URL", "http://localhost:8100").rstrip("/")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("LLM_GATEWAY_API_KEY", "")
    model = os.getenv("CHAT_MODEL", "qwen2.5-7b-instruct")

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    with httpx.Client(timeout=120.0) as client:
        # 1. Health check
        r = client.get(f"{base_url}/health")
        print(f"1. /health -> {r.status_code} {r.json()}")
        assert r.status_code == 200

        # 2. List models
        r = client.get(f"{base_url}/v1/models", headers=headers)
        print(f"2. /v1/models -> {r.status_code} ({len(r.json().get('data', []))} models)")
        assert r.status_code == 200

        # 3. Embeddings
        r = client.post(
            f"{base_url}/v1/embeddings",
            headers=headers,
            json={"model": "bge-small-en-v1.5", "input": ["B2B SaaS quarterly revenue analysis"]},
        )
        assert r.status_code == 200, r.text
        dim = len(r.json()["data"][0]["embedding"])
        print(f"3. /v1/embeddings -> {r.status_code} (vector dim={dim})")

        # 4. Chat completion
        r = client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a concise B2B analyst."},
                    {"role": "user", "content": "Reply with OK and the sum of 12000 + 18500."},
                ],
                "temperature": 0.0,
                "max_tokens": 64,
            },
        )
        assert r.status_code == 200, r.text
        content = r.json()["choices"][0]["message"]["content"]
        print(f"4. /v1/chat/completions -> {r.status_code}: {content.strip()}")

    print("ALL SELF-HOSTED LLM STACK CHECKS PASSED!")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
