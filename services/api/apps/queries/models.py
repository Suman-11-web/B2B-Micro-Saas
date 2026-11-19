"""
Query models for question answering and retrieval.
"""
import uuid
from django.db import models
from apps.accounts.models import TenantModel, Company, User


class Query(TenantModel):
    """User query/question."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    class SourceFilter(models.TextChoices):
        ALL = 'all', 'All Sources'
        DOCUMENTS = 'documents', 'Documents Only'
        DATABASE = 'database', 'Database Only'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='queries')
    question = models.TextField()
    source_filter = models.CharField(
        max_length=20,
        choices=SourceFilter.choices,
        default=SourceFilter.ALL
    )
    document_ids = models.JSONField(default=list, blank=True, help_text='Specific document IDs to search')
    data_source_ids = models.JSONField(default=list, blank=True, help_text='Specific data source IDs to query')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    idempotency_key = models.CharField(max_length=100, unique=True, db_index=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'queries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"Query: {self.question[:50]}..."


class QueryResult(TenantModel):
    """Query result with answer, citations, and chart."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.OneToOneField(Query, on_delete=models.CASCADE, related_name='result')
    answer_text = models.TextField()
    answer_structured = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(default=0.0)
    citations = models.JSONField(default=list, blank=True)
    chart_spec = models.JSONField(default=dict, blank=True)
    chart_data = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    follow_up_questions = models.JSONField(default=list, blank=True)
    tokens_input = models.PositiveIntegerField(default=0)
    tokens_output = models.PositiveIntegerField(default=0)
    model = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    feedback = models.JSONField(default=dict, blank=True)  # thumbs_up/down, comments
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'query_results'
        ordering = ['-created_at']

    def __str__(self):
        return f"Result for {self.query.question[:50]}..."


class RetrievedChunk(models.Model):
    """Track which chunks were retrieved for a query."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.ForeignKey(Query, on_delete=models.CASCADE, related_name='retrieved_chunks')
    chunk = models.ForeignKey('documents.Chunk', on_delete=models.CASCADE, related_name='retrievals')
    score = models.FloatField()
    rank = models.PositiveIntegerField()
    used_in_answer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'retrieved_chunks'
        ordering = ['query', 'rank']
        indexes = [
            models.Index(fields=['query', 'rank']),
        ]