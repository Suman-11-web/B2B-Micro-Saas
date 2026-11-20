#!/usr/bin/env python3
"""
Generate a signed HS256 JWT token for authenticating against the LLM API Gateway.
Usage:
    python scripts/generate_token.py --subject django-api --days 365
"""
from __future__ import annotations

import argparse
import os
import time

import jwt


def main():
    parser = argparse.ArgumentParser(description="Generate JWT bearer token for LLM API Gateway")
    parser.add_argument("--subject", default="b2b-django-api", help="Token subject (sub claim)")
    parser.add_argument("--days", type=int, default=365, help="Validity period in days")
    parser.add_argument("--secret", default=os.getenv("JWT_SECRET", "your-secret-key"), help="JWT signing secret")
    args = parser.parse_args()

    now = int(time.time())
    payload = {
        "sub": args.subject,
        "iat": now,
        "exp": now + (args.days * 86400),
        "scopes": ["chat", "embeddings", "rag"],
    }
    token = jwt.encode(payload, args.secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
