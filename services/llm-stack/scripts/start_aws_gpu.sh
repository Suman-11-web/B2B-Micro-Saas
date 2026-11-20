#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Checking NVIDIA GPU ==="
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "ERROR: nvidia-smi not found. For CPU-only EC2 instances, run:"
  echo "  docker compose -f docker/docker-compose.cpu.yml up -d --build"
  exit 1
fi
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

echo "=== Starting Self-Hosted GPU LLM Stack (vLLM + RAG + Gateway) ==="
docker compose -f docker/docker-compose.gpu.yml up -d --build

echo "Waiting for Gateway on http://localhost:8100/health ..."
for i in $(seq 1 40); do
  if curl -sf http://localhost:8100/health >/dev/null 2>&1; then
    echo "Gateway is UP!"
    curl -s http://localhost:8100/health
    echo ""
    echo "Point Django services/api/.env to:"
    echo '  OPENAI_BASE_URL="http://<THIS_EC2_IP>:8100/v1"'
    echo '  OPENAI_API_KEY="<LLM_GATEWAY_API_KEY from services/llm-stack/.env>"'
    echo '  CHAT_MODEL="qwen2.5-7b-instruct"'
    echo '  EMBEDDING_MODEL="bge-small-en-v1.5"'
    exit 0
  fi
  sleep 5
done

echo "Timed out waiting for LLM Gateway. Check logs with:"
echo "  docker compose -f docker/docker-compose.gpu.yml logs -f"
exit 1
