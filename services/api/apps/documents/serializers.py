"""
Serializers for documents app.
"""
from rest_framework import serializers
from apps.documents.models import Document, Chunk, DocumentProcessingLog
from apps.documents.storage import generate_presigned_upload_url, generate_presigned_download_url
from django.conf import settings


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document model."""
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)
    presigned_download_url = serializers.SerializerMethodField()
    processing_logs = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'source_type', 'filename', 'original_filename',
            'mime_type', 'file_size', 'checksum', 'status',
            'error_message', 'page_count', 'sheet_names', 'column_info',
            'metadata', 'uploaded_by', 'uploaded_by_email',
            'presigned_download_url', 'processing_logs',
            'processed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'checksum', 'status', 'error_message',
            'page_count', 'sheet_names', 'column_info',
            'uploaded_by', 'processed_at', 'created_at', 'updated_at',
        ]

    def get_presigned_download_url(self, obj):
        if obj.status == Document.Status.READY and obj.s3_key:
            return generate_presigned_download_url(obj.s3_key)
        return None

    def get_processing_logs(self, obj):
        logs = obj.processing_logs.all()[:10]
        return DocumentProcessingLogSerializer(logs, many=True).data


class DocumentCreateSerializer(serializers.Serializer):
    """Serializer for initiating document upload."""
    filename = serializers.CharField(max_length=255)
    mime_type = serializers.ChoiceField(choices=Document.MimeType.choices)
    file_size = serializers.IntegerField(min_value=1, max_value=settings.MAX_UPLOAD_SIZE)
    checksum = serializers.CharField(max_length=64)

    def validate_mime_type(self, value):
        allowed = [m.value for m in Document.MimeType]
        if value not in allowed:
            raise serializers.ValidationError(f"Unsupported file type. Allowed: {allowed}")
        return value

    def validate_file_size(self, value):
        if value > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(f"File size exceeds maximum of {settings.MAX_UPLOAD_SIZE} bytes")
        return value


class DocumentUploadResponseSerializer(serializers.Serializer):
    """Response for document upload initiation."""
    document_id = serializers.UUIDField()
    upload_url = serializers.URLField()
    upload_fields = serializers.DictField()
    expires_in = serializers.IntegerField()


class DocumentProcessingLogSerializer(serializers.ModelSerializer):
    """Serializer for DocumentProcessingLog."""

    class Meta:
        model = DocumentProcessingLog
        fields = ['id', 'step', 'status', 'message', 'duration_ms', 'metadata', 'created_at']
        read_only_fields = fields


class ChunkSerializer(serializers.ModelSerializer):
    """Serializer for Chunk model."""

    class Meta:
        model = Chunk
        fields = [
            'id', 'content', 'token_count', 'sequence_number',
            'page_number', 'sheet_name', 'row_range', 'metadata', 'created_at',
        ]
        read_only_fields = fields