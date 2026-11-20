"""
LLM API Gateway - FastAPI application for self-hosted LLM inference.
Handles authentication, rate limiting, load balancing, and request routing.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
import json
import os
import secrets
import time
import uuid

import httpx
import jwt
import structlog
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response, StreamingResponse

logger = structlog.get_logger()

# Metrics
REQUEST_COUNT = Counter('llm_requests_total', 'Total requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('llm_request_latency_seconds', 'Request latency', ['endpoint'])
ACTIVE_CONNECTIONS = Gauge('llm_active_connections', 'Active connections')
TOKEN_USAGE = Counter('llm_tokens_total', 'Total tokens', ['type', 'model'])

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM = "HS256"
INTERNAL_API_KEY = os.getenv("LLM_GATEWAY_API_KEY", "")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")
RAG_URL = os.getenv("RAG_URL", "http://localhost:8002")
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))
PORT = int(os.getenv("LLM_GATEWAY_PORT", "8100"))

# In-memory rate limiter (use Redis in production)
rate_limit_store: Dict[str, Dict[str, Any]] = {}

security = HTTPBearer()


# Models
class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: Optional[str] = ""
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="llama-3.1-8b-instruct")
    messages: List[ChatMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=8192)
    stream: bool = False
    stop: Optional[List[str]] = None
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    user: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class EmbeddingRequest(BaseModel):
    model: str = Field(default="text-embedding-3-small")
    input: Union[List[str], str]
    encoding_format: str = "float"
    dimensions: Optional[int] = None


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[Dict[str, Any]]
    model: str
    usage: Dict[str, int]


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[Dict[str, Any]]


# Rate Limiter
async def check_rate_limit(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()

    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = {"count": 0, "window_start": current_time}

    client_data = rate_limit_store[client_ip]

    if current_time - client_data["window_start"] > 60:
        client_data["count"] = 0
        client_data["window_start"] = current_time

    if client_data["count"] >= RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    client_data["count"] += 1


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if INTERNAL_API_KEY and token == INTERNAL_API_KEY:
        return {"sub": "internal-service", "scope": "all"}
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting LLM API Gateway", port=PORT, vllm_url=VLLM_URL, rag_url=RAG_URL)
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    yield
    await app.state.http_client.aclose()
    logger.info("Shutting down LLM API Gateway")


app = FastAPI(
    title="B2B Micro-SaaS LLM API Gateway",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    vllm_healthy = False
    try:
        resp = await app.state.http_client.get(f"{VLLM_URL}/health", timeout=5.0)
        vllm_healthy = resp.status_code == 200
    except Exception:
        pass

    rag_healthy = False
    try:
        resp = await app.state.http_client.get(f"{RAG_URL}/health", timeout=5.0)
        rag_healthy = resp.status_code == 200
    except Exception:
        pass

    return {
        "status": "healthy" if vllm_healthy and rag_healthy else "degraded",
        "services": {
            "vllm": "healthy" if vllm_healthy else "unhealthy",
            "rag": "healthy" if rag_healthy else "unhealthy",
        },
    }


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")


@app.get("/v1/models", response_model=ModelsResponse)
async def list_models(user: dict = Depends(verify_token)):
    """List available models."""
    now = int(time.time())
    return ModelsResponse(
        object="list",
        data=[
            {"id": "llama-3.1-8b-instruct", "object": "model", "created": now, "owned_by": "meta", "permission": [], "root": "llama-3.1-8b-instruct", "parent": None},
            {"id": "qwen2.5-7b-instruct", "object": "model", "created": now, "owned_by": "qwen", "permission": [], "root": "qwen2.5-7b-instruct", "parent": None},
            {"id": "mistral-7b-instruct", "object": "model", "created": now, "owned_by": "mistral", "permission": [], "root": "mistral-7b-instruct", "parent": None},
            {"id": "text-embedding-3-small", "object": "model", "created": now, "owned_by": "local", "permission": [], "root": "text-embedding-3-small", "parent": None},
        ],
    )


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    user: dict = Depends(verify_token),
    _rate_limit=Depends(check_rate_limit),
):
    """Chat completions endpoint compatible with OpenAI API."""
    start_time = time.time()
    request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

    vllm_request = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content or ""} for m in request.messages],
        "temperature": request.temperature,
        "top_p": request.top_p,
        "max_tokens": request.max_tokens,
        "stream": request.stream,
        "stop": request.stop,
        "presence_penalty": request.presence_penalty,
        "frequency_penalty": request.frequency_penalty,
    }

    if request.stream:
        return StreamingResponse(
            stream_chat_completion(request_id, request.model, vllm_request),
            media_type="text/event-stream",
        )

    ACTIVE_CONNECTIONS.inc()
    try:
        resp = await app.state.http_client.post(
            f"{VLLM_URL}/v1/chat/completions",
            json=vllm_request,
            timeout=300.0,
        )
        resp.raise_for_status()
        result = resp.json()

        REQUEST_COUNT.labels(endpoint="chat_completions", status="success").inc()
        TOKEN_USAGE.labels(type="prompt", model=request.model).inc(result.get("usage", {}).get("prompt_tokens", 0))
        TOKEN_USAGE.labels(type="completion", model=request.model).inc(result.get("usage", {}).get("completion_tokens", 0))
        REQUEST_LATENCY.labels(endpoint="chat_completions").observe(time.time() - start_time)

        return ChatCompletionResponse(**result)
    except httpx.HTTPStatusError as e:
        REQUEST_COUNT.labels(endpoint="chat_completions", status="error").inc()
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        REQUEST_COUNT.labels(endpoint="chat_completions", status="error").inc()
        logger.error("Chat completion error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        ACTIVE_CONNECTIONS.dec()


async def stream_chat_completion(request_id: str, model: str, vllm_request: dict) -> AsyncGenerator[str, None]:
    """Stream chat completion from vLLM."""
    try:
        async with app.state.http_client.stream(
            "POST",
            f"{VLLM_URL}/v1/chat/completions",
            json={**vllm_request, "stream": True},
            timeout=300.0,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    yield f"data: {data}\n\n"
    except Exception as e:
        logger.error("Streaming error", error=str(e))
        error_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "error"}],
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    user: dict = Depends(verify_token),
    _rate_limit=Depends(check_rate_limit),
):
    """Create embeddings endpoint compatible with OpenAI embeddings schema."""
    try:
        texts = request.input if isinstance(request.input, list) else [request.input]
        resp = await app.state.http_client.post(
            f"{RAG_URL}/embeddings",
            json={"texts": texts, "model": request.model},
            timeout=60.0,
        )
        resp.raise_for_status()
        payload = resp.json()

        # Normalize RAG service response into OpenAI-compatible EmbeddingResponse
        if "data" in payload:
            return EmbeddingResponse(**payload)

        vectors = payload.get("embeddings", [])
        data = [
            {"object": "embedding", "index": idx, "embedding": vec}
            for idx, vec in enumerate(vectors)
        ]
        total_tokens = payload.get("usage", {}).get("total_tokens", sum(len(t.split()) for t in texts))
        return EmbeddingResponse(
            object="list",
            data=data,
            model=payload.get("model", request.model),
            usage={"prompt_tokens": total_tokens, "total_tokens": total_tokens},
        )
    except Exception as e:
        logger.error("Embedding error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/rag/query")
async def rag_query(
    question: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
    user: dict = Depends(verify_token),
    _rate_limit=Depends(check_rate_limit),
):
    """Query RAG pipeline."""
    try:
        resp = await app.state.http_client.post(
            f"{RAG_URL}/query",
            json={"question": question, "top_k": top_k, "filters": filters},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("RAG query error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/rag/index")
async def index_documents(
    documents: List[Dict[str, Any]],
    user: dict = Depends(verify_token),
    _rate_limit=Depends(check_rate_limit),
):
    """Index documents in RAG."""
    try:
        resp = await app.state.http_client.post(
            f"{RAG_URL}/index",
            json={"documents": documents},
            timeout=300.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Index error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/api-keys")
async def create_api_key(
    name: str,
    scopes: Optional[List[str]] = None,
    expires_in_days: int = 365,
    user: dict = Depends(verify_token),
):
    """Create API key for external access."""
    key = f"sk-{secrets.token_urlsafe(32)}"
    return {
        "key": key,
        "name": name,
        "scopes": scopes or ["chat", "embeddings", "rag"],
        "created_by": user.get("sub"),
        "expires_at": int(time.time()) + (expires_in_days * 86400),
    }


@app.get("/admin/stats")
async def admin_stats(user: dict = Depends(verify_token)):
    """Get system statistics."""
    return {
        "active_connections": ACTIVE_CONNECTIONS._value.get(),
        "rate_limit_clients": len(rate_limit_store),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
