"""
Views for queries app.
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from apps.queries.models import Query, QueryResult, RetrievedChunk
from apps.queries.serializers import (
    QuerySerializer, QueryCreateSerializer,
    QueryResultSerializer, QueryFeedbackSerializer,
    RetrievedChunkSerializer
)
from apps.queries.tasks import process_query
from apps.accounts.permissions import BelongsToTenant, HasPermission
import uuid
import structlog

logger = structlog.get_logger()


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

        # Generate idempotency key if not provided
        idempotency_key = serializer.validated_data.get('idempotency_key') or str(uuid.uuid4())

        # Check for duplicate
        existing = Query.objects.filter(
            company=request.company,
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return Response(
                QuerySerializer(existing, context={'request': request}).data,
                status=status.HTTP_200_OK
            )

        # Create query
        query = Query.objects.create(
            company=request.company,
            user=request.user,
            question=serializer.validated_data['question'],
            source_filter=serializer.validated_data['source_filter'],
            document_ids=serializer.validated_data.get('document_ids', []),
            data_source_ids=serializer.validated_data.get('data_source_ids', []),
            idempotency_key=idempotency_key,
        )

        # Queue processing
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