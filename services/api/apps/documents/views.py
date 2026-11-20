"""
Views for documents app.
"""
import hashlib
import os
import tempfile
import uuid
from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from apps.documents.models import Document, Chunk, DocumentProcessingLog
from apps.documents.serializers import (
    DocumentSerializer, DocumentCreateSerializer,
    ChunkSerializer,
)
from apps.documents.storage import (
    generate_presigned_upload_url,
    generate_presigned_download_url,
    save_local_file,
    upload_to_s3,
)
from apps.documents.tasks import parse_document
from apps.accounts.permissions import BelongsToTenant, HasPermission
import structlog

logger = structlog.get_logger()

EXT_TO_MIME = {
    '.pdf': Document.MimeType.PDF,
    '.xlsx': Document.MimeType.XLSX,
    '.xls': Document.MimeType.XLS,
    '.csv': Document.MimeType.CSV,
    '.txt': Document.MimeType.TXT,
}


def _has_real_openai_key() -> bool:
    key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    return bool(key) and not key.startswith('sk-your-')


def _process_document_locally(document: Document, filepath: str):
    """Parse, chunk, and optionally embed a document synchronously for local dev."""
    from apps.documents.parsers import parse_pdf, parse_excel, parse_csv, parse_txt

    document.status = Document.Status.PARSING
    document.save(update_fields=['status'])

    try:
        if document.mime_type == Document.MimeType.PDF:
            parsed = parse_pdf(filepath)
        elif document.mime_type in [Document.MimeType.XLSX, Document.MimeType.XLS]:
            parsed = parse_excel(filepath)
        elif document.mime_type == Document.MimeType.CSV:
            parsed = parse_csv(filepath)
        else:
            parsed = parse_txt(filepath)

        document.page_count = parsed.get('page_count', 0)
        document.sheet_names = parsed.get('sheet_names', [])
        document.column_info = parsed.get('column_info', {})
        document.status = Document.Status.CHUNKING
        document.save()

        document.chunks.all().delete()
        created_chunks = []
        for i, chunk_data in enumerate(parsed.get('chunks', [])):
            chunk = Chunk.objects.create(
                company=document.company,
                document=document,
                content=chunk_data['content'],
                token_count=chunk_data['token_count'],
                sequence_number=i,
                page_number=chunk_data.get('page_number'),
                sheet_name=chunk_data.get('sheet_name'),
                row_range=chunk_data.get('row_range', {}),
                metadata=chunk_data.get('metadata', {}),
            )
            created_chunks.append(chunk)

        if created_chunks and _has_real_openai_key():
            try:
                from apps.documents.embeddings import generate_embeddings
                embeddings = generate_embeddings([c.content for c in created_chunks])
                for chunk, emb in zip(created_chunks, embeddings):
                    chunk.embedding = emb.tobytes()
                    chunk.save(update_fields=['embedding'])
            except Exception as emb_err:
                logger.warning("Embedding skipped (falling back to text search)", error=str(emb_err))

        document.status = Document.Status.READY
        document.processed_at = timezone.now()
        document.error_message = ''
        document.save()
    except Exception as e:
        document.status = Document.Status.FAILED
        document.error_message = str(e)
        document.save()
        logger.error("Local document processing failed", document_id=str(document.id), error=str(e))


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
        return Document.objects.filter(company=self.request.company).exclude(
            status=Document.Status.DELETED
        ).select_related('uploaded_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentCreateSerializer
        return DocumentSerializer

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """Direct multipart file upload endpoint (works with local storage or S3)."""
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'missing_file', 'message': 'Please select a file to upload.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            return Response(
                {'error': 'file_too_large', 'message': f'File exceeds maximum size of {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce company storage quota
        from django.db.models import Sum
        sub = request.company.active_subscription or request.company.subscriptions.order_by('-created_at').first()
        storage_limit = sub.plan.storage_limit_bytes if sub and sub.plan else (1024 * 1024 * 1024)
        used_bytes = Document.objects.filter(company=request.company).exclude(
            status=Document.Status.DELETED
        ).aggregate(total=Sum('file_size'))['total'] or 0
        if storage_limit > 0 and (used_bytes + uploaded_file.size) > storage_limit:
            return Response(
                {'error': 'storage_quota_exceeded', 'message': 'Storage quota exceeded for your current plan. Please upgrade via UPI Billing.'},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        # Sanitize filename to prevent path injection
        raw_name = os.path.basename(uploaded_file.name or 'document').replace('\x00', '').strip()
        filename = ''.join(ch for ch in raw_name if ch.isprintable())[:200] or 'document'
        ext = os.path.splitext(filename)[1].lower()
        mime_type = EXT_TO_MIME.get(ext)
        if not mime_type:
            return Response(
                {'error': 'unsupported_type', 'message': 'Unsupported file type. Allowed: PDF, Excel (.xlsx/.xls), CSV, TXT.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Magic-byte, zip-bomb, and macro validation
        header_bytes = uploaded_file.read(16)
        uploaded_file.seek(0)
        if ext == '.pdf' and not header_bytes.startswith(b'%PDF-'):
            return Response(
                {'error': 'invalid_magic_bytes', 'message': 'File content does not match a valid PDF header.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if ext == '.xlsx':
            if not header_bytes.startswith(b'PK\x03\x04'):
                return Response(
                    {'error': 'invalid_magic_bytes', 'message': 'File content does not match a valid XLSX archive.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            import zipfile
            try:
                with zipfile.ZipFile(uploaded_file) as zf:
                    total_uncompressed = 0
                    for info in zf.infolist():
                        if 'vbaproject.bin' in info.filename.lower():
                            return Response(
                                {'error': 'macro_blocked', 'message': 'Macro-enabled Excel files are blocked for security.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        total_uncompressed += info.file_size
                        if total_uncompressed > 150 * 1024 * 1024:
                            return Response(
                                {'error': 'zip_bomb_detected', 'message': 'Compressed spreadsheet exceeds safe decompression limit.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        if info.compress_size > 0 and (info.file_size / info.compress_size) > 100:
                            return Response(
                                {'error': 'zip_bomb_detected', 'message': 'Suspicious compression ratio detected in spreadsheet.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
            except zipfile.BadZipFile:
                return Response(
                    {'error': 'corrupt_archive', 'message': 'Invalid or corrupted XLSX archive.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            finally:
                uploaded_file.seek(0)
        if ext == '.xls' and not header_bytes.startswith(b'\xd0\xcf\x11\xe0'):
            return Response(
                {'error': 'invalid_magic_bytes', 'message': 'File content does not match a valid XLS file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Compute SHA-256 checksum
        sha256 = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            sha256.update(chunk)
        checksum = sha256.hexdigest()
        uploaded_file.seek(0)

        s3_key = f"{request.company.id}/{uuid.uuid4()}{ext}"

        from django.db import transaction
        from django.db.models import Sum
        from apps.accounts.models import Company

        with transaction.atomic():
            locked_company = Company.objects.select_for_update().get(id=request.company.id)
            sub = locked_company.active_subscription or locked_company.subscriptions.order_by('-created_at').first()
            storage_limit = sub.plan.storage_limit_bytes if sub and sub.plan else (1024 * 1024 * 1024)
            used_bytes = Document.objects.filter(company=locked_company).exclude(
                status=Document.Status.DELETED
            ).aggregate(total=Sum('file_size'))['total'] or 0
            if storage_limit > 0 and (used_bytes + uploaded_file.size) > storage_limit:
                return Response(
                    {'error': 'storage_quota_exceeded', 'message': 'Storage quota exceeded for your current plan. Please upgrade via UPI Billing.'},
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )

            document = Document.objects.create(
                company=locked_company,
                source_type=Document.SourceType.UPLOAD,
                s3_key=s3_key,
                filename=filename,
                original_filename=filename,
                mime_type=mime_type,
                file_size=uploaded_file.size,
                checksum=checksum,
                status=Document.Status.QUEUED,
                uploaded_by=request.user,
            )

        if getattr(settings, 'USE_LOCAL_STORAGE', False):
            saved_path = save_local_file(uploaded_file, s3_key)
            _process_document_locally(document, str(saved_path))
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            try:
                upload_to_s3(tmp_path, s3_key, content_type=mime_type)
                if settings.DEBUG:
                    _process_document_locally(document, tmp_path)
                else:
                    parse_document.delay(str(document.id))
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        document.refresh_from_db()
        return Response(
            DocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def create(self, request, *args, **kwargs):
        """Initiate document upload - returns presigned URL."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        filename = data['filename']
        mime_type = data['mime_type']
        file_size = data['file_size']
        checksum = data['checksum']

        ext = filename.split('.')[-1] if '.' in filename else ''
        s3_key = f"{request.company.id}/{uuid.uuid4()}.{ext}" if ext else f"{request.company.id}/{uuid.uuid4()}"
        upload_data = generate_presigned_upload_url(s3_key, mime_type)

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

        return Response({
            'document_id': document.id,
            'upload_url': upload_data['url'],
            'upload_fields': upload_data['fields'],
            'expires_in': 3600,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def confirm_upload(self, request, pk=None):
        """Confirm upload completed and start processing."""
        document = self.get_object()
        if document.status != Document.Status.QUEUED:
            return Response(
                {'error': 'invalid_status', 'message': 'Document is not in queued state.'},
                status=status.HTTP_400_BAD_REQUEST
            )
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
        url = generate_presigned_download_url(document.s3_key)
        return Response({'download_url': url, 'filename': document.original_filename})

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """Reprocess a failed or ready document."""
        document = self.get_object()
        if document.status not in [Document.Status.FAILED, Document.Status.READY]:
            return Response(
                {'error': 'invalid_status', 'message': 'Document cannot be reprocessed in current state.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        document.status = Document.Status.QUEUED
        document.error_message = ''
        document.save()
        document.chunks.all().delete()
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

    @action(detail=True, methods=['get'], url_path='chart-data')
    def chart_data(self, request, pk=None):
        """Extract chart-ready tabular series from an uploaded CSV or Excel document."""
        import pandas as pd
        from apps.documents.storage import _local_path, _use_local_storage, download_from_s3

        document = self.get_object()
        if document.mime_type not in [Document.MimeType.CSV, Document.MimeType.XLSX, Document.MimeType.XLS]:
            return Response(
                {'error': 'not_tabular', 'message': 'Chart extraction is supported for CSV and Excel files.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tmp_path = None
        try:
            if _use_local_storage():
                filepath = str(_local_path(document.s3_key))
            else:
                ext = os.path.splitext(document.filename)[1] or '.csv'
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp_path = tmp.name
                download_from_s3(document.s3_key, tmp_path)
                filepath = tmp_path

            if document.mime_type == Document.MimeType.CSV:
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)

            if df.empty:
                return Response({'filename': document.filename, 'label_key': '', 'numeric_keys': [], 'rows': []})

            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            non_numeric_cols = [c for c in df.columns.tolist() if c not in numeric_cols]
            label_key = non_numeric_cols[0] if non_numeric_cols else df.columns[0]

            rows = []
            for _, row in df.head(50).iterrows():
                item = {str(label_key): str(row[label_key])}
                for col in numeric_cols:
                    val = row[col]
                    item[str(col)] = 0 if pd.isna(val) else float(val)
                rows.append(item)

            return Response({
                'document_id': str(document.id),
                'filename': document.filename,
                'label_key': str(label_key),
                'numeric_keys': [str(c) for c in numeric_cols],
                'rows': rows,
            })
        except Exception as e:
            return Response(
                {'error': 'chart_parse_failed', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass


class ChunkViewSet(viewsets.ReadOnlyModelViewSet):
    """Chunk viewing."""
    queryset = Chunk.objects.all()
    serializer_class = ChunkSerializer
    permission_classes = [BelongsToTenant, HasPermission('view_documents')]
    filterset_fields = ['document']

    def get_queryset(self):
        return Chunk.objects.filter(company=self.request.company).select_related('document')
