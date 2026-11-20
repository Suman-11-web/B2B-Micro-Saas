"""
Views for queries app.
"""
import time
import uuid
from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.queries.models import Query, QueryResult, RetrievedChunk
from apps.queries.serializers import (
    QuerySerializer, QueryCreateSerializer,
    QueryResultSerializer, QueryFeedbackSerializer,
    RetrievedChunkSerializer
)
from apps.queries.tasks import process_query
from apps.accounts.permissions import BelongsToTenant, HasPermission
import structlog

logger = structlog.get_logger()


def _has_real_openai_key() -> bool:
    key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    return bool(key) and not key.startswith('sk-your-')


def _process_query_locally(query: Query):
    """Run retrieval + answer generation synchronously for instant local dev results."""
    from apps.queries.retrieval import Retriever, build_context
    from apps.accounts.models import UsageEvent

    start_time = time.time()
    query.status = Query.Status.PROCESSING
    query.save(update_fields=['status'])

    try:
        query_embedding = None
        if _has_real_openai_key():
            try:
                from apps.documents.embeddings import generate_single_embedding
                query_embedding = generate_single_embedding(query.question)
            except Exception as emb_err:
                logger.warning("Query embedding skipped", error=str(emb_err))

        retriever = Retriever()
        retrieved = retriever.retrieve(
            query_embedding=query_embedding,
            company_id=str(query.company.id),
            document_ids=query.document_ids or None,
            source_filter=query.source_filter,
            query_text=query.question,
        )

        if not retrieved:
            QueryResult.objects.create(
                company=query.company,
                query=query,
                answer_text="No uploaded document content was found yet. Upload a PDF, CSV, Excel, or TXT file first, then ask your question.",
                confidence=0.0,
                summary="No documents indexed yet.",
                model="local-search",
                latency_ms=int((time.time() - start_time) * 1000),
            )
            query.status = Query.Status.COMPLETED
            query.save(update_fields=['status'])
            return

        if _has_real_openai_key():
            from apps.queries.llm import generate_answer, check_grounding
            context = build_context(retrieved)
            answer = check_grounding(generate_answer(query.question, context), retrieved)
            answer_text = answer['answer']
            confidence = answer['confidence']
            citations = answer['citations']
            summary = answer['summary']
            follow_ups = answer.get('follow_up_questions', [])
            tokens_in = answer.get('tokens_input', 0)
            tokens_out = answer.get('tokens_output', 0)
            model_name = answer.get('model', settings.CHAT_MODEL)
            structured = answer
        else:
            top_snippets = []
            citations = []
            for idx, chunk in enumerate(retrieved[:3]):
                snippet = chunk['content'].strip()[:400]
                top_snippets.append(f"[{chunk['filename']}] {snippet}")
                citations.append({
                    'doc_index': idx,
                    'snippet': snippet[:200],
                    'page': chunk.get('page_number'),
                    'sheet': chunk.get('sheet_name'),
                })
            answer_text = (
                "Top matching excerpts from your documents (add a real OPENAI_API_KEY in services/api/.env for full AI synthesis):\n\n"
                + "\n\n".join(top_snippets)
            )
            confidence = round(min(0.95, max(0.3, retrieved[0]['vector_score'])), 2)
            summary = f"Found {len(retrieved)} matching chunk(s) across your uploaded documents."
            follow_ups = []
            tokens_in = 0
            tokens_out = 0
            model_name = "local-keyword-search"
            structured = {'answer': answer_text, 'citations': citations}

        for i, chunk_data in enumerate(retrieved):
            RetrievedChunk.objects.create(
                query=query,
                chunk_id=chunk_data['chunk_id'],
                score=chunk_data.get('vector_score', 0.0),
                rank=i,
                used_in_answer=i < 3,
            )

        UsageEvent.objects.create(
            company=query.company,
            user=query.user,
            event_type=UsageEvent.EventType.QUERY,
            quantity=1,
            metadata={'query_id': str(query.id), 'model': model_name},
        )

        QueryResult.objects.create(
            company=query.company,
            query=query,
            answer_text=answer_text,
            answer_structured=structured,
            confidence=confidence,
            citations=citations,
            summary=summary,
            follow_up_questions=follow_ups,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            model=model_name,
            latency_ms=int((time.time() - start_time) * 1000),
        )
        query.status = Query.Status.COMPLETED
        query.save(update_fields=['status'])

    except Exception as e:
        query.status = Query.Status.FAILED
        query.error_message = str(e)
        query.save(update_fields=['status', 'error_message'])
        logger.error("Local query processing failed", query_id=str(query.id), error=str(e))


class QueryViewSet(viewsets.ModelViewSet):
    """Query management."""
    queryset = Query.objects.all()
    serializer_class = QuerySerializer
    permission_classes = [BelongsToTenant, HasPermission('manage_queries')]
    filterset_fields = ['status', 'source_filter']
    ordering = ['-created_at']

    def get_queryset(self):
        return Query.objects.filter(company=self.request.company).select_related('user')

    def get_serializer_class(self):
        if self.action == 'create':
            return QueryCreateSerializer
        return QuerySerializer

    def create(self, request, *args, **kwargs):
        """Submit a new query."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = serializer.validated_data.get('idempotency_key') or str(uuid.uuid4())

        existing = Query.objects.filter(
            company=request.company,
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return Response(
                QuerySerializer(existing, context={'request': request}).data,
                status=status.HTTP_200_OK
            )

        # Enforce cross-tenant document_ids ownership + atomic monthly query quota
        from django.db import transaction
        from django.db.models import Sum
        from apps.accounts.models import Company, UsageEvent
        from apps.documents.models import Document

        requested_doc_ids = [str(d) for d in serializer.validated_data.get('document_ids', [])]
        if requested_doc_ids:
            owned_count = Document.objects.filter(
                company=request.company,
                id__in=requested_doc_ids,
            ).count()
            if owned_count != len(set(requested_doc_ids)):
                return Response(
                    {'error': 'forbidden_document', 'message': 'One or more document IDs do not belong to your company.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        with transaction.atomic():
            locked_company = Company.objects.select_for_update().get(id=request.company.id)
            sub = locked_company.active_subscription or locked_company.subscriptions.order_by('-created_at').first()
            query_limit = sub.plan.query_limit_monthly if sub and sub.plan else 50
            month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            used_queries = UsageEvent.objects.filter(
                company=locked_company,
                event_type=UsageEvent.EventType.QUERY,
                created_at__gte=month_start,
            ).aggregate(total=Sum('quantity'))['total'] or 0
            if query_limit > 0 and used_queries >= query_limit:
                return Response(
                    {'error': 'query_quota_exceeded', 'message': 'Monthly AI query quota reached. Please upgrade your plan in Billing & UPI.'},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

            query = Query.objects.create(
                company=locked_company,
                user=request.user,
                question=serializer.validated_data['question'],
                source_filter=serializer.validated_data['source_filter'],
                document_ids=requested_doc_ids,
                data_source_ids=serializer.validated_data.get('data_source_ids', []),
                idempotency_key=idempotency_key,
            )

        if settings.DEBUG or getattr(settings, 'USE_LOCAL_STORAGE', False):
            _process_query_locally(query)
            query.refresh_from_db()
            return Response(
                QuerySerializer(query, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )

        process_query.delay(str(query.id))
        return Response(
            QuerySerializer(query, context={'request': request}).data,
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=['post'])
    def feedback(self, request, pk=None):
        """Submit feedback on query result."""
        query = self.get_object()
        if not hasattr(query, 'result'):
            return Response(
                {'error': 'no_result', 'message': 'Query has no result yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = QueryFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = query.result
        result.feedback = {
            'rating': serializer.validated_data['rating'],
            'comment': serializer.validated_data.get('comment', ''),
            'user_id': str(request.user.id),
            'created_at': timezone.now().isoformat(),
        }
        result.save(update_fields=['feedback'])
        return Response({'message': 'Feedback recorded.'})

    @action(detail=True, methods=['get'])
    def retrieved_chunks(self, request, pk=None):
        """Get chunks retrieved for this query."""
        query = self.get_object()
        chunks = query.retrieved_chunks.select_related('chunk__document').order_by('rank')
        page = self.paginate_queryset(chunks)
        if page is not None:
            serializer = RetrievedChunkSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = RetrievedChunkSerializer(chunks, many=True)
        return Response(serializer.data)


class QueryResultViewSet(viewsets.ReadOnlyModelViewSet):
    """Query result viewing."""
    queryset = QueryResult.objects.all()
    serializer_class = QueryResultSerializer
    permission_classes = [BelongsToTenant, HasPermission('view_queries')]

    def get_queryset(self):
        return QueryResult.objects.filter(company=self.request.company).select_related('query')
