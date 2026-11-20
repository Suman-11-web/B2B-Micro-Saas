# Self-Hosted LLM Stack (`services/llm-stack`)

Production OpenAI-compatible self-hosted LLM stack for **InsightVault AI** — zero external LLM API keys required.

## Directory Structure
- `api/main.py` — FastAPI OpenAI-compatible Gateway (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`, `/v1/rag/*`, Prometheus `/metrics`, JWT + internal API key auth) on port **8100**.
- `engine/vllm_server.py` — Custom vLLM async inference server (port **8001**).
- `rag/rag_pipeline.py` — Self-hosted SentenceTransformers embeddings (`BAAI/bge-small-en-v1.5`) + CrossEncoder reranker + PostgreSQL RAG pipeline (port **8002**).
- `config/models.yaml` & `config/settings.py` — Open-weight model catalog (`Qwen2.5-7B-Instruct`, `Llama-3.1-8B-Instruct`, `Mistral-7B-Instruct`, `bge-small-en-v1.5`).
- `models/registry.py` — Hugging Face Hub real weight downloader (`python -m models.registry list|download`).
- `training/train_lora.py` & `training/sample_dataset.jsonl` — Real QLoRA/PEFT supervised fine-tuning pipeline for B2B domain adaptation.
- `docker/` — Production Dockerfiles (`Dockerfile.gateway`, `Dockerfile.rag`) and Compose stacks (`docker-compose.gpu.yml` for AWS GPU with vLLM, `docker-compose.cpu.yml` for CPU EC2 with Ollama).
- `scripts/` — JWT generator (`generate_token.py`), E2E test suite (`test_stack.py`), and AWS GPU launcher (`start_aws_gpu.sh`).

## Deploy on AWS EC2 (NVIDIA GPU — Recommended: `g5.xlarge` or `g6.xlarge`)
```bash
cd services/llm-stack
cp .env.example .env
# Edit .env and set strong JWT_SECRET and LLM_GATEWAY_API_KEY
bash scripts/start_aws_gpu.sh
```

## Deploy on AWS EC2 (CPU-Only — `t3.xlarge` / `c7i.xlarge`)
```bash
cd services/llm-stack
cp .env.example .env
docker compose -f docker/docker-compose.cpu.yml up -d --build
docker exec llm-ollama ollama pull qwen2.5:3b
```

## Connect Django (`services/api/.env`) to Your Self-Hosted LLM
```env
OPENAI_API_KEY="<LLM_GATEWAY_API_KEY from services/llm-stack/.env>"
OPENAI_BASE_URL="http://<LLM_HOST_IP>:8100/v1"
CHAT_MODEL="qwen2.5-7b-instruct"
CHAT_MODEL_FALLBACK="qwen2.5-7b-instruct"
EMBEDDING_MODEL="bge-small-en-v1.5"
```

## Verify End-to-End
```bash
LLM_GATEWAY_URL=http://localhost:8100 LLM_API_KEY="<LLM_GATEWAY_API_KEY>" python3 scripts/test_stack.py
```
