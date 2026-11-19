"""
Django admin configuration for documents app.
"""
from django.contrib import admin
from apps.documents.models import Document, Chunk, DocumentProcessingLog


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'company', 'mime_type', 'status', 'file_size', 'page_count', 'created_at']
    list_filter = ['status', 'source_type', 'mime_type', 'created_at']
    search_fields = ['filename', 's3_key']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in Document._meta.fields]


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'sequence_number', 'page_number', 'token_count', 'created_at']
    list_filter = ['created_at', 'page_number', 'sheet_name']
    search_fields = ['document__filename']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in Chunk._meta.fields]


@admin.register(DocumentProcessingLog)
class DocumentProcessingLogAdmin(admin.ModelAdmin):
    list_display = ['document', 'step', 'status', 'duration_ms', 'created_at']
    list_filter = ['step', 'status', 'created_at']
    search_fields = ['document__filename']
    ordering = ['-created_at']

    readonly_fields = [f.name for f in DocumentProcessingLog._meta.fields]