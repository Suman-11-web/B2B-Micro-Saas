"""
Document models for file upload, processing, and storage.
"""
import uuid
from django.db import models
from django.conf import settings
from apps.accounts.models import TenantModel, Company, User


class Document(TenantModel):
    """Document model for uploaded files."""
    class SourceType(models.TextChoices):
        UPLOAD = 'upload', 'Upload'
        DATABASE = 'database', 'Database'
        API = 'api', 'API'

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        PARSING = 'parsing', 'Parsing'
        CHUNKING = 'chunking', 'Chunking'
        EMBEDDING = 'embedding', 'Embedding'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'
        DELETED = 'deleted', 'Deleted'

    class MimeType(models.TextChoices):
        PDF = 'application/pdf', 'PDF'
        XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Excel (.xlsx)'
        XLS = 'application/vnd.ms-excel', 'Excel (.xls)'
        CSV = 'text/csv', 'CSV'
        TXT = 'text/plain', 'Text'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.UPLOAD)
    s3_key = models.CharField(max_length=512, db_index=True)
    filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, choices=MimeType.choices)
    file_size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64, help_text='SHA-256 checksum')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    error_message = models.TextField(blank=True, null=True)
    page_count = models.PositiveIntegerField(default=0)
    sheet_names = models.JSONField(default=list, blank=True)
    column_info = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'source_type']),
            models.Index(fields=['s3_key']),
        ]

    def __str__(self):
        return f"{self.filename} ({self.status})"

    @property
    def is_processed(self):
        return self.status == self.Status.READY

    @property
    def chunk_count(self):
        return self.chunks.count()


class Chunk(TenantModel):
    """Document chunk with embedding for vector search."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    content = models.TextField()
    token_count = models.PositiveIntegerField()
    sequence_number = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    sheet_name = models.CharField(max_length=255, blank=True, null=True)
    row_range = models.JSONField(default=dict, blank=True)
    embedding = models.BinaryField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chunks'
        ordering = ['document', 'sequence_number']
        indexes = [
            models.Index(fields=['document', 'sequence_number']),
            models.Index(fields=['company', 'document']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['document', 'sequence_number'], name='unique_chunk_seq'),
        ]

    def __str__(self):
        return f"Chunk {self.sequence_number} of {self.document.filename}"


class DocumentProcessingLog(models.Model):
    """Log for document processing steps."""
    class Step(models.TextChoices):
        DOWNLOAD = 'download', 'Download'
        VALIDATE = 'validate', 'Validate'
        PARSE = 'parse', 'Parse'
        CHUNK = 'chunk', 'Chunk'
        EMBED = 'embed', 'Embed'
        INDEX = 'index', 'Index'

    class Status(models.TextChoices):
        STARTED = 'started', 'Started'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='processing_logs')
    step = models.CharField(max_length=20, choices=Step.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'document_processing_logs'
        ordering = ['document', 'created_at']
        indexes = [
            models.Index(fields=['document', 'step']),
        ]

    def __str__(self):
        return f"{self.document.filename} - {self.step}: {self.status}"