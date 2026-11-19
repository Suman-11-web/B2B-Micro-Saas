"""
Retrieval system for query answering - hybrid vector + BM25 search.
"""
import numpy as np
from django.db import connection
from django.conf import settings
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class Retriever:
    """Hybrid retrieval: vector similarity + BM25 full-text search."""

    def __init__(self):
        self.top_k = settings.RETRIEVAL_TOP_K
        self.bm25_top_k = settings.RETRIEVAL_BM25_TOP_K
        self.final_top_k = settings.RETRIEVAL_FINAL_TOP_K

    def retrieve(
        self,
        query_embedding: np.ndarray,
        company_id: str,
        document_ids: List[str] = None,
        source_filter: str = 'all'
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks using hybrid search.
        Returns list of chunks with scores and metadata.
        """
        # Vector search
        vector_results = self._vector_search(query_embedding, company_id, document_ids, source_filter)

        # BM25 search (if we have query text, we'd use it here)
        # For now, we'll rely on vector + re-ranking
        bm25_results = self._bm25_search(company_id, document_ids, source_filter)

        # Merge and deduplicate
        merged = self._merge_results(vector_results, bm25_results)

        # Re-rank with cross-encoder if enabled
        if settings.RERANK_ENABLED and merged:
            merged = self._rerank(merged, query_embedding)

        return merged[:self.final_top_k]

    def _vector_search(
        self,
        query_embedding: np.ndarray,
        company_id: str,
        document_ids: List[str] = None,
        source_filter: str = 'all'
    ) -> List[Dict[str, Any]]:
        """Vector similarity search using pgvector."""
        embedding_bytes = query_embedding.astype(np.float32).tobytes()

        # Build filter conditions
        filters = ["c.company_id = %s"]
        params = [company_id]

        if document_ids:
            placeholders = ','.join(['%s'] * len(document_ids))
            filters.append(f"c.document_id IN ({placeholders})")
            params.extend(document_ids)

        if source_filter == 'documents':
            filters.append("d.source_type = 'upload'")
        elif source_filter == 'database':
            filters.append("d.source_type = 'database'")

        where_clause = " AND ".join(filters)

        sql = f"""
            SELECT
                c.id,
                c.document_id,
                c.content,
                c.token_count,
                c.sequence_number,
                c.page_number,
                c.sheet_name,
                c.row_range,
                c.metadata,
                d.filename,
                d.mime_type,
                1 - (c.embedding <=> %s) AS similarity
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {where_clause}
            ORDER BY c.embedding <=> %s
            LIMIT %s
        """

        with connection.cursor() as cursor:
            cursor.execute(sql, params + [embedding_bytes, embedding_bytes, self.top_k])
            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'chunk_id': str(row[0]),
                'document_id': str(row[1]),
                'content': row[2],
                'token_count': row[3],
                'sequence_number': row[4],
                'page_number': row[5],
                'sheet_name': row[6],
                'row_range': row[7],
                'metadata': row[8],
                'filename': row[9],
                'mime_type': row[10],
                'vector_score': float(row[11]),
                'source': 'vector',
            })

        return results

    def _bm25_search(
        self,
        company_id: str,
        document_ids: List[str] = None,
        source_filter: str = 'all'
    ) -> List[Dict[str, Any]]:
        """BM25 full-text search using PostgreSQL tsvector."""
        # For now, return empty - would need query text
        # This is a placeholder for BM25 implementation
        return []

    def _merge_results(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict]
    ) -> List[Dict]:
        """Merge and deduplicate results from vector and BM25."""
        # Deduplicate by chunk_id
        seen = set()
        merged = []

        for result in vector_results + bm25_results:
            chunk_id = result['chunk_id']
            if chunk_id not in seen:
                seen.add(chunk_id)
                merged.append(result)

        # Sort by score (vector_score or bm25_score)
        merged.sort(key=lambda x: x.get('vector_score', 0) + x.get('bm25_score', 0), reverse=True)

        return merged

    def _rerank(self, results: List[Dict], query_embedding: np.ndarray) -> List[Dict]:
        """Re-rank results using cross-encoder."""
        # Placeholder for cross-encoder reranking
        # In production, use a cross-encoder model
        return results


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