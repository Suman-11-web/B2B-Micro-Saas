"""
RAG Pipeline - Retrieval-Augmented Generation pipeline.
Handles document indexing, retrieval, reranking, and generation.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class DocumentInput(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}


class IndexRequest(BaseModel):
    documents: List[DocumentInput]
    batch_size: int = 32


class IndexResponse(BaseModel):
    indexed: int
    failed: int
    document_ids: List[str]


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None
    rerank: bool = True
    rerank_top_k: int = 20
    return_context: bool = True


class QueryResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]]
    contexts: Optional[List[Dict[str, Any]]] = None
    confidence: float
    processing_time_ms: int


class EmbeddingRequest(BaseModel):
    texts: List[str]
    model: str = "all-MiniLM-L6-v2"


class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    usage: Dict[str, int]


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
PGVECTOR_DSN = os.getenv("DATABASE_URL", "postgresql://b2b:b2bpassword@localhost:5432/b2b")
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:8100")
LLM_GATEWAY_API_KEY = os.getenv("LLM_GATEWAY_API_KEY", "")


@dataclass
class RetrievedChunk:
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    rank: int


class RAGPipeline:
    """Complete RAG pipeline with embedding, retrieval, reranking, and generation."""

    def __init__(self):
        self.reranker = None
        self.db_pool = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self._embed_model = None

    def _auth_headers(self) -> Dict[str, str]:
        if LLM_GATEWAY_API_KEY:
            return {"Authorization": f"Bearer {LLM_GATEWAY_API_KEY}"}
        return {}

    async def initialize(self):
        """Initialize DB pool, table schema, and optional reranker."""
        import asyncpg

        self.db_pool = await asyncpg.create_pool(PGVECTOR_DSN, min_size=2, max_size=10)
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    embedding JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )

        try:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(RERANK_MODEL, max_length=512)
        except Exception as e:
            logger.warning("CrossEncoder unavailable, skipping reranking", error=str(e))
            self.reranker = None

        self.http_client = httpx.AsyncClient(timeout=120.0)
        logger.info("RAG pipeline initialized")

    async def close(self):
        if self.db_pool:
            await self.db_pool.close()
        if self.http_client:
            await self.http_client.aclose()

    async def embed_texts(self, texts: List[str], model: str = EMBEDDING_MODEL) -> List[List[float]]:
        """Generate embeddings using local SentenceTransformer."""
        from sentence_transformers import SentenceTransformer

        if self._embed_model is None:
            self._embed_model = SentenceTransformer(EMBEDDING_MODEL)

        embeddings = self._embed_model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()

    async def index_documents(self, documents: List[DocumentInput], batch_size: int = 32) -> IndexResponse:
        """Index documents with embeddings."""
        doc_ids: List[str] = []
        failed = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            texts = [doc.content for doc in batch]
            embeddings = await self.embed_texts(texts)

            async with self.db_pool.acquire() as conn:
                for doc, embedding in zip(batch, embeddings):
                    doc_id = str(uuid.uuid4())
                    try:
                        await conn.execute(
                            """
                            INSERT INTO rag_documents (id, content, metadata, embedding)
                            VALUES ($1, $2, $3::jsonb, $4::jsonb)
                            """,
                            doc_id,
                            doc.content,
                            json.dumps(doc.metadata),
                            json.dumps(embedding),
                        )
                        doc_ids.append(doc_id)
                    except Exception as e:
                        logger.error("Failed to insert document", error=str(e))
                        failed += 1

        return IndexResponse(indexed=len(doc_ids), failed=failed, document_ids=doc_ids)

    async def retrieve(
        self, question: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """Retrieve relevant chunks using full-text search and cosine similarity."""
        import numpy as np

        query_vec = np.array((await self.embed_texts([question]))[0], dtype=np.float32)
        query_norm = float(np.linalg.norm(query_vec)) or 1.0

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, content, metadata, embedding FROM rag_documents LIMIT 500")

        chunks: List[RetrievedChunk] = []
        for row in rows:
            score = 0.0
            if row["embedding"]:
                emb_list = json.loads(row["embedding"]) if isinstance(row["embedding"], str) else row["embedding"]
                emb_vec = np.array(emb_list, dtype=np.float32)
                denom = float(np.linalg.norm(emb_vec)) * query_norm
                if denom > 0 and emb_vec.shape == query_vec.shape:
                    score = float(np.dot(emb_vec, query_vec) / denom)

            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {})
            chunks.append(RetrievedChunk(id=row["id"], content=row["content"], metadata=meta, score=score, rank=0))

        chunks.sort(key=lambda x: x.score, reverse=True)
        for i, chunk in enumerate(chunks[:top_k]):
            chunk.rank = i
        return chunks[:top_k]

    async def rerank_chunks(self, question: str, chunks: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]:
        """Rerank chunks using cross-encoder when available."""
        if not chunks or self.reranker is None:
            return chunks[:top_k]

        pairs = [(question, chunk.content) for chunk in chunks]
        scores = self.reranker.predict(pairs, batch_size=16)

        for chunk, score in zip(chunks, scores):
            chunk.score = float(score)

        chunks.sort(key=lambda x: x.score, reverse=True)
        for i, chunk in enumerate(chunks[:top_k]):
            chunk.rank = i
        return chunks[:top_k]

    async def generate_answer(self, question: str, chunks: List[RetrievedChunk]) -> Tuple[str, List[Dict[str, Any]], float]:
        """Generate answer using self-hosted LLM gateway."""
        context_parts = []
        citations = []

        for i, chunk in enumerate(chunks):
            context_parts.append(f"[DOC_{i+1}] {chunk.content}")
            citations.append({
                "doc_id": chunk.id,
                "snippet": chunk.content[:200],
                "score": chunk.score,
                "metadata": chunk.metadata,
            })

        context = "\n\n".join(context_parts)
        prompt = (
            "You are a helpful business analyst. Answer the question based ONLY on the provided context.\n"
            f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer with citations using [DOC_N] format."
        )

        try:
            resp = await self.http_client.post(
                f"{LLM_API_URL}/v1/chat/completions",
                headers=self._auth_headers(),
                json={
                    "model": os.getenv("CHAT_MODEL", "llama-3.1-8b-instruct"),
                    "messages": [
                        {"role": "system", "content": "You are a helpful business analyst. Answer based only on provided context."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "stream": False,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            result = resp.json()
            answer = result["choices"][0]["message"]["content"]
            return answer, citations, 0.9
        except Exception as e:
            logger.error("Answer generation failed", error=str(e))
            return "I couldn't generate an answer based on the available context.", citations, 0.0

    async def query(self, request: QueryRequest) -> QueryResponse:
        start = time.time()
        chunks = await self.retrieve(request.question, top_k=request.rerank_top_k if request.rerank else request.top_k)
        chunks = await self.rerank_chunks(request.question, chunks, request.top_k) if request.rerank else chunks[:request.top_k]
        answer, citations, confidence = await self.generate_answer(request.question, chunks)

        contexts = (
            [{"id": c.id, "content": c.content, "score": c.score, "metadata": c.metadata} for c in chunks]
            if request.return_context
            else None
        )
        return QueryResponse(
            answer=answer,
            citations=citations,
            contexts=contexts,
            confidence=confidence,
            processing_time_ms=int((time.time() - start) * 1000),
        )


app = FastAPI(title="RAG Pipeline", version="1.0.0")
rag_pipeline = RAGPipeline()


@app.on_event("startup")
async def startup():
    await rag_pipeline.initialize()


@app.on_event("shutdown")
async def shutdown():
    await rag_pipeline.close()


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    embeddings = await rag_pipeline.embed_texts(request.texts, request.model)
    return EmbeddingResponse(
        embeddings=embeddings,
        model=request.model,
        usage={"total_tokens": sum(len(t.split()) for t in request.texts)},
    )


@app.post("/index", response_model=IndexResponse)
async def index_documents(request: IndexRequest, background_tasks: BackgroundTasks):
    return await rag_pipeline.index_documents(request.documents, request.batch_size)


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    return await rag_pipeline.query(request)


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Stream RAG response."""
    async def generate():
        chunks = await rag_pipeline.retrieve(request.question, top_k=20)
        chunks = await rag_pipeline.rerank_chunks(request.question, chunks, request.top_k)
        context = "\n\n".join([f"[DOC_{i+1}] {c.content}" for i, c in enumerate(chunks[:5])])

        async with rag_pipeline.http_client.stream(
            "POST",
            f"{LLM_API_URL}/v1/chat/completions",
            headers=rag_pipeline._auth_headers(),
            json={
                "model": os.getenv("CHAT_MODEL", "llama-3.1-8b-instruct"),
                "messages": [
                    {"role": "system", "content": "Answer based on context."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {request.question}\n\nAnswer with citations."},
                ],
                "temperature": 0.1,
                "max_tokens": 1024,
                "stream": True,
            },
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    yield f"data: {data}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("RAG_PORT", "8002")))
