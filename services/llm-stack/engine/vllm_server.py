"""
vLLM Inference Server - High-performance LLM inference engine.
Supports multiple models, LoRA adapters, and batched inference (Linux + NVIDIA CUDA).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams

logger = structlog.get_logger()


class CompletionRequest(BaseModel):
    model: str
    prompt: str
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 2048
    stop: Optional[List[str]] = None
    stream: bool = False
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    logprobs: Optional[int] = None
    n: int = 1
    best_of: Optional[int] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: Optional[int] = 2048
    stream: bool = False
    stop: Optional[List[str]] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None
    n: int = 1
    user: Optional[str] = None


class LoRAConfig(BaseModel):
    name: str
    path: str
    rank: int = 16


class ModelConfig(BaseModel):
    model: str
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 4096
    dtype: str = "auto"
    trust_remote_code: bool = True
    enforce_eager: bool = False
    quantization: Optional[str] = None
    load_format: str = "auto"
    lora_modules: List[LoRAConfig] = []


engine: Optional[AsyncLLMEngine] = None

AVAILABLE_MODELS: Dict[str, ModelConfig] = {
    "llama-3.1-8b-instruct": ModelConfig(
        model=os.getenv("VLLM_PRIMARY_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
        tensor_parallel_size=int(os.getenv("VLLM_TP_SIZE", "1")),
        max_model_len=8192,
    ),
    "qwen2.5-7b-instruct": ModelConfig(
        model="Qwen/Qwen2.5-7B-Instruct",
        tensor_parallel_size=1,
        max_model_len=32768,
    ),
    "mistral-7b-instruct": ModelConfig(
        model="mistralai/Mistral-7B-Instruct-v0.3",
        tensor_parallel_size=1,
        max_model_len=8192,
    ),
}


async def initialize_engine():
    """Initialize vLLM engine with the configured primary model."""
    global engine

    primary_key = os.getenv("VLLM_MODEL_KEY", "llama-3.1-8b-instruct")
    config = AVAILABLE_MODELS.get(primary_key, next(iter(AVAILABLE_MODELS.values())))

    engine_args = AsyncEngineArgs(
        model=config.model,
        tensor_parallel_size=config.tensor_parallel_size,
        gpu_memory_utilization=config.gpu_memory_utilization,
        max_model_len=config.max_model_len,
        dtype=config.dtype,
        trust_remote_code=config.trust_remote_code,
        enforce_eager=config.enforce_eager,
        quantization=config.quantization,
        load_format=config.load_format,
        enable_lora=bool(config.lora_modules),
        max_loras=max(1, len(config.lora_modules)) if config.lora_modules else 1,
        max_lora_rank=max((m.rank for m in config.lora_modules), default=16),
    )

    engine = AsyncLLMEngine.from_engine_args(engine_args)
    logger.info("vLLM engine initialized", model=config.model)


def create_sampling_params(request: Union[CompletionRequest, ChatCompletionRequest]) -> SamplingParams:
    """Create sampling params from request."""
    return SamplingParams(
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_tokens or 2048,
        stop=request.stop,
        presence_penalty=getattr(request, 'presence_penalty', 0.0),
        frequency_penalty=getattr(request, 'frequency_penalty', 0.0),
        n=getattr(request, 'n', 1),
    )


app = FastAPI(title="vLLM Inference Server", version="1.0.0")


@app.on_event("startup")
async def startup():
    await initialize_engine()


@app.get("/health")
async def health():
    return {"status": "healthy" if engine is not None else "initializing", "models": list(AVAILABLE_MODELS.keys())}


@app.get("/v1/models")
async def list_models():
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": now,
                "owned_by": config.model.split("/")[0],
                "permission": [],
                "root": model_id,
                "parent": None,
                "max_model_len": config.max_model_len,
            }
            for model_id, config in AVAILABLE_MODELS.items()
        ],
    }


@app.post("/v1/completions")
async def completions(request: CompletionRequest):
    """Text completions endpoint."""
    if engine is None:
        raise HTTPException(status_code=503, detail="vLLM engine not initialized")
    if request.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {request.model} not found")

    sampling_params = create_sampling_params(request)
    request_id = f"cmpl-{uuid.uuid4().hex[:29]}"

    if request.stream:
        return StreamingResponse(
            stream_completion(request.prompt, request.model, request_id, sampling_params),
            media_type="text/event-stream",
        )

    final_output = None
    async for request_output in engine.generate(request.prompt, sampling_params, request_id=request_id):
        final_output = request_output

    if final_output is None:
        raise HTTPException(status_code=500, detail="No output generated")

    choices = [
        {
            "text": out.text,
            "index": i,
            "logprobs": out.logprobs if request.logprobs else None,
            "finish_reason": out.finish_reason,
        }
        for i, out in enumerate(final_output.outputs)
    ]

    prompt_tokens = len(final_output.prompt_token_ids)
    completion_tokens = sum(len(o.token_ids) for o in final_output.outputs)

    return {
        "id": request_id,
        "object": "text_completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": choices,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def stream_completion(
    prompt: str, model: str, request_id: str, sampling_params: SamplingParams
) -> AsyncGenerator[str, None]:
    """Stream completion tokens as incremental deltas."""
    previous_text = ""
    async for request_output in engine.generate(prompt, sampling_params, request_id=request_id):
        out = request_output.outputs[0]
        delta_text = out.text[len(previous_text):]
        previous_text = out.text
        chunk = {
            "id": request_id,
            "object": "text_completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "text": delta_text,
                "index": 0,
                "finish_reason": out.finish_reason,
            }],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Chat completions endpoint (OpenAI compatible)."""
    if engine is None:
        raise HTTPException(status_code=503, detail="vLLM engine not initialized")
    if request.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {request.model} not found")

    prompt = format_chat_messages(request.messages)
    sampling_params = create_sampling_params(request)
    request_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"

    if request.stream:
        return StreamingResponse(
            stream_chat_completion(prompt, request.model, request_id, sampling_params),
            media_type="text/event-stream",
        )

    final_output = None
    async for request_output in engine.generate(prompt, sampling_params, request_id=request_id):
        final_output = request_output

    if final_output is None:
        raise HTTPException(status_code=500, detail="No output generated")

    choices = [
        {
            "index": i,
            "message": {"role": "assistant", "content": out.text},
            "finish_reason": out.finish_reason,
        }
        for i, out in enumerate(final_output.outputs)
    ]

    prompt_tokens = len(final_output.prompt_token_ids)
    completion_tokens = sum(len(o.token_ids) for o in final_output.outputs)

    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": choices,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def stream_chat_completion(
    prompt: str, model: str, request_id: str, sampling_params: SamplingParams
) -> AsyncGenerator[str, None]:
    """Stream chat completion tokens as incremental deltas."""
    previous_text = ""
    async for request_output in engine.generate(prompt, sampling_params, request_id=request_id):
        out = request_output.outputs[0]
        delta_text = out.text[len(previous_text):]
        previous_text = out.text
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": delta_text},
                "finish_reason": out.finish_reason,
            }],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


def format_chat_messages(messages: List[Dict[str, str]]) -> str:
    """Format chat messages using Llama-3 Instruct chat template."""
    prompt = "<|begin_of_text|>"
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        prompt += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
    prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
    return prompt


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
        loop_mode = "uvloop"
    except ImportError:
        loop_mode = "auto"
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("VLLM_PORT", "8001")), loop=loop_mode)
