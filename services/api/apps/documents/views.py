"""
Views for documents app.
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.db.models import Q
from apps.documents.models import Document, Chunk, DocumentProcessingLog
from apps.documents.serializers import (
    DocumentSerializer, DocumentCreateSerializer,
    DocumentUploadResponseSerializer, ChunkSerializer,
    DocumentProcessingLogSerializer
)
from apps.documents.storage import generate_presigned_upload_url
from apps.documents.tasks import parse_document
from apps.accounts.permissions import BelongsToTenant, HasPermission
import uuid
import structlog

logger = structlog.get_logger()


class DocumentViewSet(viewsets.ModelViewSet):
    """Document management."""
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [BelongsToTenant, HasPermission('manage_documents')]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ['status', 'source_type', 'mime_type']
    search_fields = ['filename', 'original_filename']
    ordering = ['-created_at']

    def get_queryset(self):
        return Document.objects.filter(company=self.request.company).select_related('uploaded_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentCreateSerializer
        return DocumentSerializer

    def create(self, request, *args, **kwargs):
        """Initiate document upload - returns presigned URL."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        filename = data['filename']
        mime_type = data['mime_type']
        file_size = data['file_size']
        checksum = data['checksum']

        # Generate unique S3 key
        ext = filename.split('.')[-1] if '.' in filename else ''
        s3_key = f"{request.company.id}/{uuid.uuid4()}.{ext}" if ext else f"{request.company.id}/{uuid.uuid4()}"

        # Generate presigned URL
        upload_data = generate_presigned_upload_url(s3_key, mime_type)

        # Create document record
        document = Document.objects.create(
            company=request.company,
            source_type=Document.SourceType.UPLOAD,
            s3_key=s3_key,
            filename=filename,
            original_filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            checksum=checksum,
            status=Document.Status.QUEUED,
            uploaded_by=request.user,
        )

        response_data = {
            'document_id': document.id,
            'upload_url': upload_data['url'],
            'upload_fields': upload_data['fields'],
            'expires_in': 3600,
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def confirm_upload(self, request, pk=None):
        """Confirm upload completed and start processing."""
        document = self.get_object()

        if document.status != Document.Status.QUEUED:
            return Response(
                {'error': 'invalid_status', 'message': 'Document is not in queued state.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Queue parsing task
        parse_document.delay(str(document.id))

        return Response({'message': 'Processing started.', 'document_id': str(document.id)})

    @action(detail=True, methods=['get'])
    def chunks(self, request, pk=None):
        """Get document chunks."""
        document = self.get_object()
        chunks = document.chunks.all().order_by('sequence_number')
        page = self.paginate_queryset(chunks)
        if page is not None:
            serializer = ChunkSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ChunkSerializer(chunks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Get presigned download URL."""
        document = self.get_object()

        if document.status != Document.Status.READY:
            return Response(
                {'error': 'not_ready', 'message': 'Document is not ready for download.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.documents.storage import generate_presigned_download_url
        url = generate_presigned_download_url(document.s3_key)

        return Response({'download_url': url, 'filename': document.original_filename})

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """Reprocess a failed document."""
        document = self.get_object()

        if document.status not in [Document.Status.FAILED, Document.Status.READY]:
            return Response(
                {'error': 'invalid_status', 'message': 'Document cannot be reprocessed in current state.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reset status and clear error
        document.status = Document.Status.QUEUED
        document.error_message = ''
        document.save()

        # Delete existing chunks
        document.chunks.all().delete()

        # Queue parsing
        parse_document.delay(str(document.id))

        return Response({'message': 'Reprocessing started.', 'document_id': str(document.id)})

    @action(detail=False, methods=['get'])
    def storage_usage(self, request):
        """Get storage usage for current company."""
        from django.db.models import Sum
        total_size = Document.objects.filter(
            company=request.company
        ).exclude(status=Document.Status.DELETED).aggregate(
            total=Sum('file_size')
        )['total'] or 0

        doc_count = Document.objects.filter(
            company=request.company
        ).exclude(status=Document.Status.DELETED).count()

        return Response({
            'total_bytes': total_size,
            'total_mb': round(total_size / (1024 * 1024), 2),
            'document_count': doc_count,
        })


class ChunkViewSet(viewsets.ReadOnlyModelViewSet):
    """Chunk viewing."""
    queryset = Chunk.objects.all()
    serializer_class = ChunkSerializer
    permission_classes = [BelongsToTenant, HasPermission('view_documents')]
    filterset_fields = ['document']

    def get_queryset(self):
        return Chunk.objects.filter(company=self.request.company).select_related('document')