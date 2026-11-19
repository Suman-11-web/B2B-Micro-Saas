"""
Serializers for queries app.
"""
from rest_framework import serializers
from apps.queries.models import Query, QueryResult, RetrievedChunk
from apps.documents.serializers import ChunkSerializer


class QuerySerializer(serializers.ModelSerializer):
    """Serializer for Query model."""
    result = serializers.SerializerMethodField()

    class Meta:
        model = Query
        fields = [
            'id', 'question', 'source_filter', 'document_ids',
            'data_source_ids', 'status', 'error_message',
            'idempotency_key', 'result', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'error_message', 'created_at', 'updated_at']

    def get_result(self, obj):
        if hasattr(obj, 'result'):
            return QueryResultSerializer(obj.result).data
        return None


class QueryCreateSerializer(serializers.Serializer):
    """Serializer for creating a query."""
    question = serializers.CharField(max_length=5000)
    source_filter = serializers.ChoiceField(
        choices=Query.SourceFilter.choices,
        default=Query.SourceFilter.ALL
    )
    document_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )
    data_source_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )
    idempotency_key = serializers.CharField(max_length=100, required=False)

    def validate_question(self, value):
        if not value.strip():
            raise serializers.ValidationError("Question cannot be empty.")
        return value.strip()

    def validate_idempotency_key(self, value):
        if value and Query.objects.filter(idempotency_key=value).exists():
            raise serializers.ValidationError("Duplicate request.")
        return value


class QueryResultSerializer(serializers.ModelSerializer):
    """Serializer for QueryResult model."""
    citations_detail = serializers.SerializerMethodField()

    class Meta:
        model = QueryResult
        fields = [
            'id', 'answer_text', 'answer_structured', 'confidence',
            'citations', 'citations_detail', 'chart_spec', 'chart_data',
            'summary', 'follow_up_questions',
            'tokens_input', 'tokens_output', 'model', 'latency_ms',
            'feedback', 'created_at',
        ]
        read_only_fields = fields

    def get_citations_detail(self, obj):
        citations = obj.citations
        detailed = []
        for c in citations:
            doc_index = c.get('doc_index', 0)
            detailed.append({
                **c,
                'doc_index': doc_index,
            })
        return detailed


class QueryFeedbackSerializer(serializers.Serializer):
    """Serializer for query feedback."""
    rating = serializers.ChoiceField(choices=[('up', 'Up'), ('down', 'Down')])
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class RetrievedChunkSerializer(serializers.ModelSerializer):
    """Serializer for RetrievedChunk."""
    chunk = ChunkSerializer(read_only=True)

    class Meta:
        model = RetrievedChunk
        fields = ['id', 'chunk', 'score', 'rank', 'used_in_answer', 'created_at']
        read_only_fields = fields