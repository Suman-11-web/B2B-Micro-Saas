"""
Retrieval system for query answering - hybrid NumPy vector + keyword search.
"""
import re
import numpy as np
from django.conf import settings
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class Retriever:
    """Hybrid retrieval: NumPy cosine similarity over stored embeddings + keyword scoring."""

    def __init__(self):
        self.top_k = settings.RETRIEVAL_TOP_K
        self.final_top_k = settings.RETRIEVAL_FINAL_TOP_K

    def retrieve(
        self,
        query_embedding: Optional[np.ndarray],
        company_id: str,
        document_ids: List[str] = None,
        source_filter: str = 'all',
        query_text: str = '',
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a company using vector + keyword scoring."""
        from apps.documents.models import Chunk

        qs = Chunk.objects.filter(company_id=company_id).select_related('document')
        if document_ids:
            qs = qs.filter(document_id__in=document_ids)
        if source_filter == 'documents':
            qs = qs.filter(document__source_type='upload')
        elif source_filter == 'database':
            qs = qs.filter(document__source_type='database')

        query_terms = [t for t in re.findall(r'\w+', (query_text or '').lower()) if len(t) > 2]

        scored = []
        for chunk in qs[:500]:
            vec_score = 0.0
            if query_embedding is not None and chunk.embedding:
                try:
                    emb = np.frombuffer(bytes(chunk.embedding), dtype=np.float32)
                    if emb.shape == query_embedding.shape:
                        denom = float(np.linalg.norm(emb) * np.linalg.norm(query_embedding))
                        if denom > 0:
                            vec_score = float(np.dot(emb, query_embedding) / denom)
                except Exception:
                    vec_score = 0.0

            kw_score = 0.0
            if query_terms:
                content_lower = chunk.content.lower()
                hits = sum(1 for term in query_terms if term in content_lower)
                kw_score = hits / len(query_terms)

            combined = vec_score if query_embedding is not None and vec_score > 0 else kw_score
            if query_embedding is not None and kw_score > 0:
                combined = 0.7 * vec_score + 0.3 * kw_score

            scored.append({
                'chunk_id': str(chunk.id),
                'document_id': str(chunk.document_id),
                'content': chunk.content,
                'token_count': chunk.token_count,
                'sequence_number': chunk.sequence_number,
                'page_number': chunk.page_number,
                'sheet_name': chunk.sheet_name,
                'row_range': chunk.row_range,
                'metadata': chunk.metadata,
                'filename': chunk.document.filename,
                'mime_type': chunk.document.mime_type,
                'vector_score': float(combined),
                'source': 'hybrid',
            })

        scored.sort(key=lambda x: x['vector_score'], reverse=True)
        # If there are chunks, return top matches (even if score is 0 so LLM/fallback still has context)
        return scored[:self.final_top_k]


def build_context(retrieved_chunks: List[Dict], max_tokens: int = 4000) -> str:
    """Build context string from retrieved chunks with citations."""
    context_parts = []
    total_tokens = 0

    for i, chunk in enumerate(retrieved_chunks):
        citation_marker = f"[DOC_{i+1}]"
        chunk_text = f"{citation_marker} Source: {chunk['filename']}"
        if chunk.get('page_number'):
            chunk_text += f", Page: {chunk['page_number']}"
        if chunk.get('sheet_name'):
            chunk_text += f", Sheet: {chunk['sheet_name']}"
        chunk_text += f"\n{chunk['content']}\n"

        chunk_tokens = chunk.get('token_count', len(chunk_text) // 4)
        if total_tokens + chunk_tokens > max_tokens:
            break

        context_parts.append(chunk_text)
        total_tokens += chunk_tokens

    return "\n---\n".join(context_parts)
