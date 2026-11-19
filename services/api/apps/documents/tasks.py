"""
Celery tasks for document processing pipeline.
"""
import hashlib
import tempfile
import os
import magic
from celery import shared_task
from django.utils import timezone
from apps.accounts.models import UsageEvent
import structlog

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def parse_document(self, document_id):
    """Parse document and extract text/content."""
    from apps.documents.models import Document, DocumentProcessingLog, Chunk
    from apps.documents.parsers import parse_pdf, parse_excel, parse_csv

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.error("Document not found", document_id=document_id)
        return

    log = DocumentProcessingLog.objects.create(
        document=document,
        step=DocumentProcessingLog.Step.PARSE,
        status=DocumentProcessingLog.Status.STARTED,
    )

    try:
        # Download from S3
        from apps.documents.storage import download_from_s3
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(document.filename)[1]) as tmp:
            download_from_s3(document.s3_key, tmp.name)
            tmp_path = tmp.name

        # Validate file
        validate_file(tmp_path, document)

        # Parse based on mime type
        start = timezone.now()
        if document.mime_type == Document.MimeType.PDF:
            chunks_data = parse_pdf(tmp_path)
        elif document.mime_type in [Document.MimeType.XLSX, Document.MimeType.XLS]:
            chunks_data = parse_excel(tmp_path)
        elif document.mime_type in [Document.MimeType.CSV, Document.MimeType.TXT]:
            chunks_data = parse_csv(tmp_path)
        else:
            raise ValueError(f"Unsupported mime type: {document.mime_type}")

        duration = (timezone.now() - start).total_seconds() * 1000

        # Update document
        document.page_count = chunks_data.get('page_count', 0)
        document.sheet_names = chunks_data.get('sheet_names', [])
        document.column_info = chunks_data.get('column_info', {})
        document.status = Document.Status.CHUNKING
        document.save()

        log.status = DocumentProcessingLog.Status.COMPLETED
        log.duration_ms = int(duration)
        log.metadata = {'chunks_found': len(chunks_data.get('chunks', []))}
        log.save()

        # Create chunk records
        for i, chunk_data in enumerate(chunks_data.get('chunks', [])):
            Chunk.objects.create(
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

        # Queue embedding task
        embed_chunks.delay(str(document.id))

    except Exception as e:
        log.status = DocumentProcessingLog.Status.FAILED
        log.message = str(e)
        log.save()

        document.status = Document.Status.FAILED
        document.error_message = str(e)
        document.save()

        logger.error("Document parsing failed", document_id=document_id, error=str(e))
        raise self.retry(exc=e)

    finally:
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def validate_file(filepath, document):
    """Validate file type and size."""
    # Check magic bytes
    mime = magic.from_file(filepath, mime=True)
    allowed_mimes = [m.value for m in Document.MimeType]
    if mime not in allowed_mimes:
        raise ValueError(f"Invalid file type: {mime}")

    # Check size
    actual_size = os.path.getsize(filepath)
    if actual_size != document.file_size:
        raise ValueError(f"File size mismatch: expected {document.file_size}, got {actual_size}")

    # Verify checksum
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    if sha256_hash.hexdigest() != document.checksum:
        raise ValueError("Checksum verification failed")


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def embed_chunks(self, document_id):
    """Generate embeddings for document chunks."""
    from apps.documents.models import Document, Chunk, DocumentProcessingLog
    from apps.documents.embeddings import generate_embeddings

    try:
        document = Document.objects.get(id=document_id)
        chunks = document.chunks.all().order_by('sequence_number')
    except Document.DoesNotExist:
        logger.error("Document not found for embedding", document_id=document_id)
        return

    log = DocumentProcessingLog.objects.create(
        document=document,
        step=DocumentProcessingLog.Step.EMBED,
        status=DocumentProcessingLog.Status.STARTED,
    )

    try:
        document.status = Document.Status.EMBEDDING
        document.save()

        texts = [chunk.content for chunk in chunks]
        embeddings = generate_embeddings(texts)

        # Save embeddings
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding.tobytes()
            chunk.save(update_fields=['embedding'])

        # Record usage
        UsageEvent.objects.create(
            company=document.company,
            event_type=UsageEvent.EventType.EMBEDDING,
            quantity=len(chunks),
            metadata={'document_id': str(document.id)}
        )

        document.status = Document.Status.READY
        document.processed_at = timezone.now()
        document.save()

        log.status = DocumentProcessingLog.Status.COMPLETED
        log.metadata = {'chunks_embedded': len(chunks)}
        log.save()

        logger.info("Document embedding completed", document_id=document_id, chunks=len(chunks))

    except Exception as e:
        log.status = DocumentProcessingLog.Status.FAILED
        log.message = str(e)
        log.save()

        document.status = Document.Status.FAILED
        document.error_message = str(e)
        document.save()

        logger.error("Document embedding failed", document_id=document_id, error=str(e))
        raise self.retry(exc=e)


@shared_task
def delete_document(document_id):
    """Delete document and associated data."""
    from apps.documents.models import Document
    from apps.documents.storage import delete_from_s3

    try:
        document = Document.objects.get(id=document_id)
        delete_from_s3(document.s3_key)
        document.status = Document.Status.DELETED
        document.save()
    except Document.DoesNotExist:
        pass