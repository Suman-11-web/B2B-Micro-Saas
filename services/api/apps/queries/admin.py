"""
Django admin configuration for queries app.
"""
from django.contrib import admin
from apps.queries.models import Query, QueryResult, RetrievedChunk


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ['question', 'company', 'user', 'status', 'idempotency_key', 'created_at']
    list_filter = ['status', 'source_filter', 'created_at']
    search_fields = ['question', 'user__email', 'company__name']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in Query._meta.fields]


@admin.register(QueryResult)
class QueryResultAdmin(admin.ModelAdmin):
    list_display = ['query', 'confidence', 'model', 'tokens_input', 'tokens_output', 'created_at']
    list_filter = ['model', 'created_at']
    search_fields = ['query__question']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in QueryResult._meta.fields]


@admin.register(RetrievedChunk)
class RetrievedChunkAdmin(admin.ModelAdmin):
    list_display = ['query', 'chunk', 'score', 'rank', 'used_in_answer']
    list_filter = ['used_in_answer', 'rank']
    search_fields = ['query__question', 'chunk__document__filename']
    ordering = ['rank']

    readonly_fields = [f.name for f in RetrievedChunk._meta.fields]