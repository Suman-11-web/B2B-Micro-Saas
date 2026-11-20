"""
S3 storage operations for document upload/download with local filesystem fallback.
"""
import os
import shutil
from pathlib import Path
import boto3
from botocore.config import Config
from django.conf import settings
import structlog

logger = structlog.get_logger()


def _use_local_storage() -> bool:
    return bool(getattr(settings, 'USE_LOCAL_STORAGE', False))


def _local_path(key: str) -> Path:
    base = (Path(settings.MEDIA_ROOT) / 'uploads').resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = (base / key).resolve()
    # Prevent path traversal outside MEDIA_ROOT/uploads
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("Invalid storage path: path traversal detected.")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def get_s3_client():
    """Get configured S3 client."""
    return boto3.client(
        's3',
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        endpoint_url=settings.AWS_S3_ENDPOINT or None,
        config=Config(
            signature_version='s3v4',
            retries={'max_attempts': 3},
        ),
    )


def generate_presigned_upload_url(key: str, content_type: str, expires_in: int = 3600) -> dict:
    """Generate presigned URL for direct browser upload (or local endpoint in dev)."""
    if _use_local_storage():
        return {
            'url': '/api/v1/documents/upload/',
            'fields': {'key': key, 'Content-Type': content_type},
        }

    s3 = get_s3_client()
    conditions = [
        {"bucket": settings.AWS_S3_BUCKET},
        ["starts-with", "$key", key],
        {"Content-Type": content_type},
        ["content-length-range", 0, settings.MAX_UPLOAD_SIZE],
    ]

    post = s3.generate_presigned_post(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=conditions,
        ExpiresIn=expires_in,
    )

    return {
        'url': post['url'],
        'fields': post['fields'],
    }


def generate_presigned_download_url(key: str, expires_in: int = 3600) -> str:
    """Generate presigned URL for download (or local media URL in dev)."""
    if _use_local_storage():
        return f"/{settings.MEDIA_URL.lstrip('/')}uploads/{key}"

    s3 = get_s3_client()
    return s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.AWS_S3_BUCKET, 'Key': key},
        ExpiresIn=expires_in,
    )


def save_local_file(uploaded_file, key: str) -> Path:
    """Save a Django UploadedFile to local storage."""
    target = _local_path(key)
    with open(target, 'wb') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)
    return target


def upload_to_s3(filepath: str, key: str, content_type: str = None, metadata: dict = None) -> bool:
    """Upload file to S3 or local storage."""
    if _use_local_storage():
        target = _local_path(key)
        shutil.copy2(filepath, target)
        logger.info("File saved to local storage", key=key)
        return True

    s3 = get_s3_client()
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    if metadata:
        extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
    if settings.AWS_KMS_KEY_ID:
        extra_args['ServerSideEncryption'] = 'aws:kms'
        extra_args['SSEKMSKeyId'] = settings.AWS_KMS_KEY_ID

    try:
        s3.upload_file(filepath, settings.AWS_S3_BUCKET, key, ExtraArgs=extra_args)
        logger.info("File uploaded to S3", key=key)
        return True
    except Exception as e:
        logger.error("S3 upload failed", key=key, error=str(e))
        return False


def download_from_s3(key: str, filepath: str) -> bool:
    """Download file from S3 or local storage."""
    if _use_local_storage():
        source = _local_path(key)
        if not source.exists():
            raise FileNotFoundError(f"Local file not found: {key}")
        shutil.copy2(source, filepath)
        logger.info("File copied from local storage", key=key)
        return True

    s3 = get_s3_client()
    try:
        s3.download_file(settings.AWS_S3_BUCKET, key, filepath)
        logger.info("File downloaded from S3", key=key)
        return True
    except Exception as e:
        logger.error("S3 download failed", key=key, error=str(e))
        return False


def delete_from_s3(key: str) -> bool:
    """Delete file from S3 or local storage."""
    if _use_local_storage():
        target = _local_path(key)
        if target.exists():
            os.unlink(target)
        return True

    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
        logger.info("File deleted from S3", key=key)
        return True
    except Exception as e:
        logger.error("S3 delete failed", key=key, error=str(e))
        return False


def check_s3_object_exists(key: str) -> bool:
    """Check if object exists in S3 or local storage."""
    if _use_local_storage():
        return _local_path(key).exists()

    s3 = get_s3_client()
    try:
        s3.head_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
        return True
    except Exception:
        return False
