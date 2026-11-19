"""
Celery tasks for query processing.
"""
import time
import numpy as np
from celery import shared_task
from django.utils import timezone
from apps.accounts.models import UsageEvent
from apps.documents.embeddings import generate_single_embedding
from apps.queries.retrieval import Retriever, build_context
from apps.queries.llm import generate_answer, check_grounding
import structlog

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_query(self, query_id):
    """Process a query: retrieve context, generate answer, save result."""
    from apps.queries.models import Query, QueryResult, RetrievedChunk
    from apps.documents.models import Chunk

    start_time = time.time()

    try:
        query = Query.objects.get(id=query_id)
    except Query.DoesNotExist:
        logger.error("Query not found", query_id=query_id)
        return

    query.status = Query.Status.PROCESSING
    query.save()

    try:
        # Generate query embedding
        query_embedding = generate_single_embedding(query.question)

        # Retrieve relevant chunks
        retriever = Retriever()
        document_ids = query.document_ids if query.document_ids else None
        retrieved = retriever.retrieve(
            query_embedding=query_embedding,
            company_id=str(query.company.id),
            document_ids=document_ids,
            source_filter=query.source_filter,
        )

        if not retrieved:
            # No relevant context found
            result = QueryResult.objects.create(
                company=query.company,
                query=query,
                answer_text="I couldn't find any relevant information to answer your question. Please try uploading relevant documents or connecting a database.",
                confidence=0.0,
                summary="No relevant context found.",
                tokens_input=0,
                tokens_output=0,
                model="none",
                latency_ms=int((time.time() - start_time) * 1000),
            )
            query.status = Query.Status.COMPLETED
            query.save()
            return

        # Build context
        context = build_context(retrieved)

        # Generate answer
        answer = generate_answer(query.question, context)

        # Verify grounding
        answer = check_grounding(answer, retrieved)

        # Save retrieved chunks
        for i, chunk_data in enumerate(retrieved):
            RetrievedChunk.objects.create(
                query=query,
                chunk_id=chunk_data['chunk_id'],
                score=chunk_data.get('vector_score', 0),
                rank=i,
                used_in_answer=any(
                    c.get('doc_index') == i for c in answer.get('citations', [])
                ),
            )

        # Record usage
        UsageEvent.objects.create(
            company=query.company,
            user=query.user,
            event_type=UsageEvent.EventType.QUERY,
            quantity=1,
            metadata={
                'query_id': str(query.id),
                'tokens_in': answer.get('tokens_input', 0),
                'tokens_out': answer.get('tokens_output', 0),
                'model': answer.get('model', ''),
            }
        )

        # Create result
        latency_ms = int((time.time() - start_time) * 1000)
        result = QueryResult.objects.create(
            company=query.company,
            query=query,
            answer_text=answer['answer'],
            answer_structured=answer,
            confidence=answer['confidence'],
            citations=answer['citations'],
            chart_spec=answer.get('chart', {}).get('spec', {}),
            chart_data=answer.get('chart', {}).get('data', {}),
            summary=answer['summary'],
            follow_up_questions=answer.get('follow_up_questions', []),
            tokens_input=answer.get('tokens_input', 0),
            tokens_output=answer.get('tokens_output', 0),
            model=answer.get('model', ''),
            latency_ms=latency_ms,
        )

        query.status = Query.Status.COMPLETED
        query.save()

        # Check if analytics needed
        if answer.get('requires_analytics'):
            from apps.analytics.tasks import run_analytics
            run_analytics.delay(str(query.id), answer.get('analysis_type'), retrieved)

        logger.info("Query processed", query_id=query_id, latency_ms=latency_ms, confidence=answer['confidence'])

    except Exception as e:
        query.status = Query.Status.FAILED
        query.error_message = str(e)
        query.save()

        logger.error("Query processing failed", query_id=query_id, error=str(e))
        raise self.retry(exc=e)


@shared_task
def process_query_stream(query_id):
    """Process query with streaming (for SSE)."""
    # This would be implemented for real-time streaming
    # For now, delegates to process_query
    return process_query.delay(query_id)